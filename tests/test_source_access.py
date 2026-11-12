import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app import scraper


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.source=scraper.source_by_id('ar-studbook')
        self.url=self.source['url']+'/ejemplares/perfil/1/example'

    def test_403_reports_source_access_denial_not_a_generic_connection_failure(self):
        with patch('app.scraper.authorize_public'), patch('app.scraper.download', side_effect=HTTPError(self.url,403,'Forbidden',{},None)):
            with self.assertRaisesRegex(scraper.ScrapeError,r'HTTP 403'):
                scraper.fetch_public(self.url,self.source)

    def test_human_check_returned_with_200_is_not_a_pedigree(self):
        html='<html><title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/check"></script></html>'
        with patch('app.scraper.authorize_public'), patch('app.scraper.download',return_value=html):
            with self.assertRaisesRegex(scraper.ScrapeError,'verificación humana'):
                scraper.fetch_public(self.url,self.source)

    def test_human_check_in_robots_does_not_become_an_allow_all_policy(self):
        with patch.dict(scraper._policies,clear=True),patch('app.scraper.download',return_value='<title>Just a moment...</title>'):
            with self.assertRaisesRegex(scraper.ScrapeError,'robots.txt'):
                scraper.authorize_public(self.url,self.source)
            self.assertFalse(scraper._policies)

    def test_a_legitimate_robots_captcha_path_is_not_a_human_challenge(self):
        robots='User-agent: *\nDisallow: /captcha/\nAllow: /ejemplares/\n'
        with patch.dict(scraper._policies,clear=True),patch('app.scraper.download',return_value=robots):
            scraper.authorize_public(self.url,self.source)
