import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from creative_signal.apify_ads import fetch_ads, facebook_page_url, POLL_LIMIT
from creative_signal.common import write_json
from creative_signal.config import call_limits, load_config, plan
from creative_signal.http import Transport, RunHalted
from creative_signal.providers import normalize_ads, required_keys


class RecordedTransport:
    def __init__(self, output):
        self.output = output
        self.calls = []
        self.counts = dict.fromkeys(['ads', 'apify_status', 'apify_dataset', 'public_web'], 0)
        self.status = 'SUCCEEDED'
        self.rows = [{"adArchiveID": "1234", "pageID": "5678", "pageName": "Brand",
                      "isActive": True, "snapshot": {"pageProfileUri": "https://www.facebook.com/brand/",
                      "cards": [{"linkUrl": "https://brand.example/product"}]}}]
        self.home = '<a href="https://www.facebook.com/brand">Facebook</a>'
        self.item_count = None

    def credential(self, name):
        return 'synthetic-token'

    def web(self, url):
        self.counts['public_web'] += 1
        value = {'url': url, 'http_status': 200, 'text': self.home, 'evidence_file': 'evidence/home.json'}
        write_json(self.output / 'evidence/home.json', value)
        return value

    def api(self, provider, url, **kwargs):
        self.calls.append((provider, url, kwargs))
        self.counts[provider] += 1
        if provider in {'ads', 'apify_status'}:
            value = {'data': {'id': 'run123', 'defaultDatasetId': 'dataset123', 'status': self.status}}
        elif '/items?' in url:
            value = self.rows
        else:
            value = {'data': {'itemCount': len(self.rows) if self.item_count is None else self.item_count}}
        write_json(self.output / f'evidence/{provider}-{self.counts[provider]:04d}.json', value)
        return value


class ApifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        self.transport = RecordedTransport(self.output)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'proof.toml')
        self.checks = self.config['checks']

    def fetch(self):
        return fetch_ads(self.transport, 'brand.example', 'ALL', self.checks)

    def test_run_limits_inputs_identity_and_native_evidence(self):
        result = normalize_ads(self.fetch(), 'brand.example')
        self.assertEqual(result['status'], 'observed_active')
        self.assertEqual(result['matched_active_ads'], 1)
        self.assertEqual(result['examples'][0]['source_url'], 'https://www.facebook.com/ads/library/?id=1234')
        self.assertIsNone(result['provider_reported_count'])
        self.assertFalse(result['complete'])
        start = self.transport.calls[0]
        query = parse_qs(urlparse(start[1]).query)
        self.assertEqual(query['maxTotalChargeUsd'], ['0.145'])
        self.assertEqual(query['restartOnError'], ['false'])
        self.assertEqual(query['build'], ['0.0.378'])
        self.assertNotIn('token', query)
        body = start[2]['body']
        self.assertEqual(body['resultsLimit'], 25)
        self.assertEqual(body['activeStatus'], 'active')
        self.assertEqual(len(body['startUrls']), 1)
        self.assertFalse(body['enrichWithEcommerceData'])
        self.assertFalse(body['isDetailsPerAd'])
        self.assertEqual(self.transport.counts['ads'], 1)
        self.assertTrue((self.output / 'apify-runs/run123.json').is_file())

    def test_no_paid_call_without_unambiguous_corporate_page(self):
        for html in ['', '<a href="https://www.facebook.com/sharer.php?u=brand">Share</a>',
                     '<a href="https://www.facebook.com/a">A</a><a href="https://www.facebook.com/b">B</a>']:
            self.transport.home = html
            result = normalize_ads(self.fetch(), 'brand.example')
            self.assertEqual(result['status'], 'unknown')
            self.assertIsNone(result['provider_reported_count'])
        self.assertEqual(self.transport.counts['ads'], 0)

    def test_company_search_uses_name_and_landing_domain_without_homepage(self):
        checks = {**self.checks, 'ad_lookup': 'company_search'}
        result = normalize_ads(fetch_ads(self.transport, 'brand.example', 'ALL', checks, company_name='Brand'), 'brand.example')
        self.assertEqual(result['status'], 'observed_active')
        self.assertEqual(self.transport.counts['public_web'], 0)
        url = self.transport.calls[0][2]['body']['startUrls'][0]['url']
        self.assertEqual(parse_qs(urlparse(url).query)['q'], ['Brand'])
        self.assertEqual(parse_qs(urlparse(url).query)['search_type'], ['keyword_exact_phrase'])
        self.transport.rows[0]['pageName'] = 'Unrelated Brand'
        result = normalize_ads(fetch_ads(self.transport, 'brand.example', 'ALL', checks, company_name='Brand'), 'brand.example')
        self.assertEqual(result['status'], 'unknown')

    def test_empty_page_summary_and_lagging_metadata_reconcile_same_run(self):
        self.transport.rows = [{"inputUrl": "https://www.facebook.com/brand", "totalCount": 0,
                                "results": [], "isResultComplete": True,
                                "pageInfo": {"page": {"id": "5678", "name": "Brand"}, "xfbAdLibraryIsCaptchaRequired": False}}]
        original = self.transport.api
        metadata_reads = []
        def stale_once(provider, url, **kwargs):
            value = original(provider, url, **kwargs)
            if provider == 'apify_dataset' and '/items?' not in url:
                metadata_reads.append(url)
                if len(metadata_reads) == 1:
                    return {'data': {'itemCount': 0}}
            return value
        self.transport.api = stale_once
        result = normalize_ads(self.fetch(), 'brand.example')
        self.assertEqual(result['status'], 'none_observed')
        self.assertEqual(result['provider_reported_count'], 0)
        self.assertEqual(result['matched_active_ads'], 0)
        self.assertFalse(result['complete'])
        self.assertEqual(self.transport.counts['ads'], 1)
        self.assertEqual(self.transport.counts['apify_dataset'], 3)
        for field, value in [('inputUrl', 'https://www.facebook.com/other'), ('isResultComplete', False)]:
            old = self.transport.rows[0][field]
            self.transport.rows[0][field] = value
            self.assertEqual(normalize_ads(self.fetch(), 'brand.example')['status'], 'unknown')
            self.transport.rows[0][field] = old

    def test_dataset_budget_checked_before_paid_start(self):
        self.transport.limits = {'apify_dataset': 4}
        self.transport.counts['apify_dataset'] = 3
        with self.assertRaises(RunHalted):
            self.fetch()
        self.assertEqual(self.transport.counts['ads'], 0)

    def test_persistently_lagging_metadata_preserves_bounded_observations(self):
        self.transport.item_count = 0
        result = normalize_ads(self.fetch(), 'brand.example')
        self.assertEqual(result['status'], 'observed_active')
        self.assertEqual(result['raw_dataset_rows'], 1)
        self.assertEqual(result['dataset_metadata_count'], 0)
        self.assertTrue(result['dataset_metadata_lagged'])
        self.assertFalse(result['complete'])
        self.assertEqual(self.transport.counts['ads'], 1)
        self.assertEqual(self.transport.counts['apify_dataset'], 3)

    def test_missing_dataset_rows_still_halt(self):
        self.transport.item_count = 2
        with self.assertRaises(RunHalted):
            self.fetch()
        self.assertEqual(self.transport.counts['ads'], 1)

    def test_two_accounts_have_room_for_both_metadata_readbacks(self):
        self.transport.limits = call_limits(self.config)
        original = self.transport.api
        def delayed(provider, url, **kwargs):
            self.assertLess(self.transport.counts[provider], self.transport.limits[provider])
            value = original(provider, url, **kwargs)
            if provider == 'apify_dataset' and self.transport.counts[provider] % 3 == 1:
                return {'data': {'itemCount': 0}}
            return value
        self.transport.api = delayed
        for _ in range(2):
            self.assertEqual(normalize_ads(self.fetch(), 'brand.example')['status'], 'observed_active')
        self.assertEqual(self.transport.counts['ads'], 2)
        self.assertEqual(self.transport.counts['apify_dataset'], 6)

    def test_wrong_page_wrong_domain_and_inactive_records_do_not_qualify(self):
        original = copy.deepcopy(self.transport.rows)
        for field in ['page', 'domain', 'inactive', 'missing_active', 'conflicting_page_ids']:
            self.transport.rows = copy.deepcopy(original)
            row = self.transport.rows[0]
            if field == 'page': row['snapshot']['pageProfileUri'] = 'https://www.facebook.com/unrelated'
            if field == 'domain': row['snapshot']['cards'][0]['linkUrl'] = 'https://unrelated.example/product'
            if field == 'inactive': row['isActive'] = False
            if field == 'missing_active': row.pop('isActive')
            if field == 'conflicting_page_ids': row['snapshot']['pageId'] = '9999'
            result = normalize_ads(self.fetch(), 'brand.example')
            self.assertNotEqual(result['status'], 'observed_active')
            self.assertIsNone(result['provider_reported_count'])

    def test_failed_running_error_and_oversized_results_halt_without_restart(self):
        for status in ['FAILED', 'RUNNING']:
            self.transport = RecordedTransport(self.output)
            self.transport.status = status
            with self.assertRaises(RunHalted): self.fetch()
            self.assertEqual(self.transport.counts['ads'], 1)
            self.assertLessEqual(self.transport.counts['apify_status'], POLL_LIMIT)
            self.assertEqual(self.transport.counts['apify_dataset'], 0)
        self.transport = RecordedTransport(self.output)
        self.transport.item_count = 26
        with self.assertRaises(RunHalted): self.fetch()
        self.assertEqual(self.transport.counts['apify_dataset'], 1)
        self.transport = RecordedTransport(self.output)
        self.transport.rows = [{'error': 'blocked'}]
        with self.assertRaises(RunHalted): self.fetch()
        self.assertEqual(self.transport.counts['ads'], 1)

    def test_plan_and_credentials_follow_selected_provider(self):
        self.assertIn('APIFY_TOKEN', required_keys(self.config))
        self.assertNotIn('ADYNTEL_API_KEY', required_keys(self.config))
        p = plan(self.config)
        self.assertEqual(p['max_ad_records'], 50)
        self.assertEqual(p['known_variable_cost_estimates']['apify_max_charge_usd'], .29)
        self.assertEqual(call_limits(self.config)['apify_dataset'], 6)
        text = (Path(__file__).resolve().parents[1] / 'proof.toml').read_text()
        bad = self.output / 'bad.toml'
        for old, new in [('ads_per_account = 25', 'ads_per_account = 26'),
                         ('apify_max_charge_usd = 0.145', 'apify_max_charge_usd = 1.0'),
                         ('meta_country = "ALL"', 'meta_country = "GB"')]:
            bad.write_text(text.replace(old, new))
            with self.assertRaises(ValueError): load_config(bad)

    def test_list_responses_and_token_redaction(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'[{"value":"secret-apify-token"}]'
        class Opener:
            def open(self, *args, **kwargs): return Response()
        with patch.dict(os.environ, {'APIFY_TOKEN': 'secret-apify-token'}), patch('urllib.request.build_opener', return_value=Opener()):
            t = Transport(self.output, {'apify_dataset': 1})
            result = t.api('apify_dataset', 'https://api.apify.com/v2/datasets/example/items', response_type='list')
        self.assertEqual(result, [{'value': '[REDACTED]'}])
        self.assertNotIn('secret-apify-token', (self.output / 'evidence/apify_dataset-0001.json').read_text())


if __name__ == '__main__':
    unittest.main()
