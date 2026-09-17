import hashlib
import hmac
import json
import unittest
from receiver import validate


class SignatureTests(unittest.TestCase):
    def payload(self, **changes):
        return dict(repository={'full_name': 'mohammad-alajlouni/mazad'},
                    ref='refs/heads/main', after='a' * 40, **changes)

    def check_payload(self, payload, event='push', signature=None):
        body = json.dumps(payload, ensure_ascii=False).encode()
        if signature is None:
            signature = 'sha256=' + hmac.new(b'secret', body, hashlib.sha256).hexdigest()
        return validate(body, signature, event, 'secret', 'mohammad-alajlouni/mazad')

    def test_signed_unicode_push(self):
        self.assertEqual(self.check_payload(self.payload(message='اختبار'))[0], 202)

    def test_missing_bad_and_non_ascii_signature(self):
        for signature in ['', 'sha256=' + '0' * 64, 'غير صحيح']:
            self.assertEqual(self.check_payload(self.payload(), signature=signature)[0], 403)

    def test_wrong_repository(self):
        payload = self.payload()
        payload['repository'] = {'full_name': 'another/repo'}
        self.assertEqual(self.check_payload(payload)[0], 403)

    def test_non_main_and_branch_deletion(self):
        payload = self.payload()
        payload['ref'] = 'refs/heads/feature'
        self.assertIsNone(self.check_payload(payload)[2])
        self.assertIsNone(self.check_payload(self.payload(deleted=True))[2])

    def test_invalid_sha_and_payload(self):
        payload = self.payload()
        payload['after'] = ';id'
        self.assertEqual(self.check_payload(payload)[0], 400)
        self.assertEqual(self.check_payload([])[0], 400)

    def test_ping_and_other_events(self):
        self.assertEqual(self.check_payload(self.payload(), event='ping')[:2], (200, 'pong'))
        self.assertIsNone(self.check_payload(self.payload(), event='issues')[2])


if __name__ == '__main__':
    unittest.main()
