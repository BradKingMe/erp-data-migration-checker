import json
import tempfile
import unittest
from pathlib import Path
from erp_migration_checker.engine import DataError, compare_files, _read_csv, _parse_decimal
from erp_migration_checker.config import ConfigError, load_config

class EngineAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='migration-engine-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def write(self, name, data):
        p = self.root / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p
    def config(self, **changes):
        raw = {'keys':[{'source':'id','target':'id'}], 'fields':[{'source':'amount','target':'amount','type':'decimal','tolerance':'0.01'}]}
        raw.update(changes)
        return load_config(self.write('mapping.json',json.dumps(raw)))
    def test_rejects_malformed_and_invalid_encoding(self):
        for data in [b'id,amount\na,"unterminated', b'id,amount\na,\xff', b'id,amount\na,\x00', b'id,id\na,1', b'id,\na,1']:
            with self.subTest(data=data), self.assertRaises(DataError):
                _read_csv(self.write('bad.csv',data))
    def test_required_headers_are_checked_even_with_no_rows(self):
        with self.assertRaisesRegex(DataError,'missing mapped'):
            compare_files(self.write('s.csv','id,other\n'),self.write('t.csv','id,amount\n'),self.config())
    def test_tolerance_is_exact_and_values_are_private(self):
        config = self.config()
        report = compare_files(self.write('s.csv','id,amount\nA,10000000000000000000000000001.01\n'),self.write('t.csv','id,amount\nA,10000000000000000000000000001.02\n'), config)
        self.assertEqual(report.status,'PASS')
        self.assertNotIn('100000000',json.dumps(report.to_dict()))
    def test_duplicates_are_not_paired_and_truncation_cannot_pass(self):
        report = compare_files(self.write('s.csv','id,amount\nA,1\nA,2\n,3\nB,4\n'),self.write('t.csv','id,amount\nA,1\n'),self.config(max_findings=1))
        self.assertEqual(report.matched_key_count,0)
        self.assertEqual(report.duplicate_source_groups,1)
        self.assertTrue(report.findings_truncated)
        self.assertEqual(report.status,'FAIL')
    def test_numeric_resource_bounds_and_finite_values(self):
        for value in ['1e100000000','NaN','Infinity','9'*1001]:
            self.assertIsNone(_parse_decimal(value))
        with self.assertRaises(ConfigError):
            self.config(fields=[{'source':'amount','target':'amount','type':'decimal','tolerance':'1e100000000'}])
    def test_invalid_config_encoding(self):
        with self.assertRaises(ConfigError):
            load_config(self.write('mapping.json',b'\xff'))

if __name__ == '__main__': unittest.main()
