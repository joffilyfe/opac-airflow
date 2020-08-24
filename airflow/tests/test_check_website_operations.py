from unittest import TestCase
from unittest.mock import patch, call

from airflow import DAG

from operations.check_website_operations import (
    concat_website_url_and_uri_list_items,
    check_uri_list,
    check_website_uri_list,
    get_webpage_href_and_src,
    not_found_expected_uri_items_in_web_page,
    get_document_webpage_uri,
    get_document_webpage_uri_list,
)


class TestConcatWebsiteUrlAndUriListItems(TestCase):

    def test_concat_website_url_and_uri_list_items_for_none_website_url_and_none_uri_list_returns_empty_list(self):
        items = concat_website_url_and_uri_list_items(None, None)
        self.assertEqual([], items)

    def test_concat_website_url_and_uri_list_items_for_none_website_url_returns_empty_list(self):
        items = concat_website_url_and_uri_list_items(None, ['uri'])
        self.assertEqual([], items)

    def test_concat_website_url_and_uri_list_items_for_none_uri_list_returns_empty_list(self):
        items = concat_website_url_and_uri_list_items(['website'], None)
        self.assertEqual([], items)

    def test_concat_website_url_and_uri_list_items_returns_list(self):
        items = concat_website_url_and_uri_list_items(
            ['website1', 'website2'],
            ['/uri1', '/uri2'])
        self.assertEqual(
            ['website1/uri1',
             'website1/uri2',
             'website2/uri1',
             'website2/uri2', ],
            items)


class MockResponse:

    def __init__(self, code):
        self.status_code = code


class MockLogger:

    def __init__(self):
        self._info = []
        self._debug = []

    def info(self, msg):
        self._info.append(msg)

    def debug(self, msg):
        self._debug.append(msg)


class TestCheckUriList(TestCase):

    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_200_returns_empty_list(self, mock_req_head):
        mock_req_head.side_effect = [MockResponse(200), MockResponse(200), ]
        uri_list = ["goodURI1", "goodURI2", ]
        result = check_uri_list(uri_list)
        self.assertEqual([], result)

    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_301_returns_empty_list(self, mock_req_head):
        mock_req_head.side_effect = [MockResponse(301)]
        uri_list = ["URI"]
        result = check_uri_list(uri_list)
        self.assertEqual([], result)

    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_302_returns_empty_list(self, mock_req_head):
        mock_req_head.side_effect = [MockResponse(302)]
        uri_list = ["URI"]
        result = check_uri_list(uri_list)
        self.assertEqual([], result)

    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_404_returns_failure_list(self, mock_req_head):
        mock_req_head.side_effect = [MockResponse(404)]
        uri_list = ["BAD_URI"]
        result = check_uri_list(uri_list)
        self.assertEqual(
            uri_list,
            result)

    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_429_returns_failure_list(self, mock_req_head):
        mock_req_head.side_effect = [MockResponse(429), MockResponse(404)]
        uri_list = ["BAD_URI"]
        result = check_uri_list(uri_list)
        self.assertEqual(
            uri_list,
            result)

    @patch('operations.check_website_operations.retry_after')
    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_200_after_retries_returns_failure_list(self, mock_req_head, mock_retry_after):
        mock_retry_after.return_value = [
            0.1, 0.2, 0.4, 0.8, 1,
        ]
        mock_req_head.side_effect = [
            MockResponse(429),
            MockResponse(502),
            MockResponse(503),
            MockResponse(504),
            MockResponse(500),
            MockResponse(200),
        ]
        uri_list = ["GOOD_URI"]
        result = check_uri_list(uri_list)
        self.assertEqual([], result)

    @patch('operations.check_website_operations.retry_after')
    @patch('operations.check_website_operations.requests.head')
    def test_check_uri_list_for_status_code_404_after_retries_returns_failure_list(self, mock_req_head, mock_retry_after):
        mock_retry_after.return_value = [
            0.1, 0.2, 0.4, 0.8, 1,
        ]
        mock_req_head.side_effect = [
            MockResponse(429),
            MockResponse(502),
            MockResponse(404),
        ]
        uri_list = ["BAD_URI"]
        result = check_uri_list(uri_list)
        self.assertEqual(["BAD_URI"], result)


class TestCheckWebsiteUriList(TestCase):

    def test_check_website_uri_list_raises_value_error_because_website_urls_are_missing(self):
        with self.assertRaises(ValueError):
            check_website_uri_list('/path/uri_list_file_path.lst', [])

    @patch("operations.check_website_operations.Logger.info")
    @patch("operations.check_website_operations.read_file")
    def test_check_website_uri_list_informs_zero_uri(self, mock_read_file, mock_info):
        mock_read_file.return_value = []
        uri_list_file_path = "/tmp/uri_list_2010-10-09.lst"
        website_url_list = ["http://www.scielo.br", "https://newscielo.br"]
        check_website_uri_list(uri_list_file_path, website_url_list)
        self.assertEqual(
            mock_info.call_args_list,
            [
                call('Quantidade de URI: %i', 0),
                call("Encontrados: %i/%i", 0, 0),
            ]
        )

    @patch("operations.check_website_operations.Logger.info")
    @patch("operations.check_website_operations.requests.head")
    @patch("operations.check_website_operations.read_file")
    def test_check_website_uri_list_informs_that_all_were_found(self, mock_read_file, mock_head, mock_info):
        mock_read_file.return_value = (
            "/scielo.php?script=sci_serial&pid=0001-3765\n"
            "/scielo.php?script=sci_issues&pid=0001-3765\n"
            "/scielo.php?script=sci_issuetoc&pid=0001-376520200005\n"
            "/scielo.php?script=sci_arttext&pid=S0001-37652020000501101\n"
        ).split()
        mock_head.side_effect = [
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
        ]
        uri_list_file_path = "/tmp/uri_list_2010-10-09.lst"
        website_url_list = ["http://www.scielo.br", "https://newscielo.br"]
        check_website_uri_list(uri_list_file_path, website_url_list)
        self.assertEqual(
            mock_info.call_args_list,
            [
                call('Quantidade de URI: %i', 8),
                call("Encontrados: %i/%i", 8, 8),
            ]
        )

    @patch("operations.check_website_operations.Logger.info")
    @patch("operations.check_website_operations.requests.head")
    @patch("operations.check_website_operations.read_file")
    def test_check_website_uri_list_informs_that_some_of_uri_items_were_not_found(self, mock_read_file, mock_head, mock_info):
        mock_read_file.return_value = (
            "/scielo.php?script=sci_serial&pid=0001-3765\n"
            "/scielo.php?script=sci_issues&pid=0001-3765\n"
            "/scielo.php?script=sci_issuetoc&pid=0001-376520200005\n"
            "/scielo.php?script=sci_arttext&pid=S0001-37652020000501101"
        ).split()
        mock_head.side_effect = [
            MockResponse(200),
            MockResponse(404),
            MockResponse(200),
            MockResponse(200),
            MockResponse(500),
            MockResponse(404),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
            MockResponse(200),
        ]
        uri_list_file_path = "/tmp/uri_list_2010-10-09.lst"
        website_url_list = ["http://www.scielo.br", "https://newscielo.br"]
        check_website_uri_list(uri_list_file_path, website_url_list)
        bad_uri_1 = "http://www.scielo.br/scielo.php?script=sci_issues&pid=0001-3765"
        bad_uri_2 = "https://newscielo.br/scielo.php?script=sci_serial&pid=0001-3765"

        self.assertEqual(
            mock_info.call_args_list,
            [
                call('Quantidade de URI: %i', 8),
                call("Retry to access '%s' after %is", bad_uri_2, 5),
                call("The URL '%s' returned the status code '%s' after %is",
                     bad_uri_2, 404, 5),
                call("Não encontrados (%i/%i):\n%s", 2, 8,
                     "\n".join([
                        bad_uri_1,
                        bad_uri_2,
                    ])),
            ]
        )


class TestGetWebpageHrefAndSrc(TestCase):

    def test_get_webpage_href_and_src_returns_src_and_href(self):
        content = """<root>
            <img src="bla.jpg"/>
            <p><x src="g.jpg"/></p>
            <a href="d.jpg"/>
            </root>"""
        expected = {
            "href": ["d.jpg"],
            "src": ["bla.jpg", "g.jpg"],
        }
        result = get_webpage_href_and_src(content)
        self.assertEqual(expected, result)

    def test_get_webpage_href_and_src_returns_src(self):
        content = """<root>
            <p><img src="bla.jpg"/></p><x src="g.jpg"/>
            </root>"""
        expected = {
            "href": [],
            "src": ["bla.jpg", "g.jpg"],
        }
        result = get_webpage_href_and_src(content)
        self.assertEqual(expected, result)

    def test_get_webpage_href_and_src_returns_href(self):
        content = '<root><a href="d.jpg"/></root>'
        expected = {
            "href": ["d.jpg"],
            "src": [],
        }
        result = get_webpage_href_and_src(content)
        self.assertEqual(expected, result)


class TestNotFoundExpectedUriItemsInWebPage(TestCase):

    def test_not_found_expected_uri_items_in_web_page_returns_empty_set(self):
        expected_uri_items = [
            "a.png",
            "b.png",
        ]
        web_page_uri_items = [
            "a.png",
            "b.png",
        ]
        result = not_found_expected_uri_items_in_web_page(
            expected_uri_items, web_page_uri_items)
        self.assertEqual(set(), result)

    def test_not_found_expected_uri_items_in_web_page_returns_a_b(self):
        expected_uri_items = [
            "a.png",
            "b.png",
        ]
        web_page_uri_items = [
            "x.png",
            "y.png",
        ]
        result = not_found_expected_uri_items_in_web_page(
            expected_uri_items, web_page_uri_items)
        self.assertEqual({"a.png", "b.png"}, result)

    def test_not_found_expected_uri_items_in_web_page_returns_b(self):
        expected_uri_items = [
            "a.png",
            "b.png",
        ]
        web_page_uri_items = [
            "a.png",
            "y.png",
        ]
        result = not_found_expected_uri_items_in_web_page(
            expected_uri_items, web_page_uri_items)
        self.assertEqual({"b.png"}, result)


class TestGetDocumentUri(TestCase):

    def test_get_document_webpage_uri_returns_uri_with_all_the_parameters(self):
        data = {
            "acron": "abcdef", "doc_id": "klamciekdoalei", "format": "x",
            "lang": "vv"
        }
        expected = "/j/abcdef/a/klamciekdoalei?format=x&lang=vv"
        result = get_document_webpage_uri(data)
        self.assertEqual(expected, result)

    def test_get_document_webpage_uri_returns_uri_without_lang(self):
        data = {
            "acron": "abcdef", "doc_id": "klamciekdoalei", "format": "x",
        }
        expected = "/j/abcdef/a/klamciekdoalei?format=x"
        result = get_document_webpage_uri(data)
        self.assertEqual(expected, result)

    def test_get_document_webpage_uri_returns_uri_without_format(self):
        data = {
            "acron": "abcdef", "doc_id": "klamciekdoalei",
            "lang": "vv"
        }
        expected = "/j/abcdef/a/klamciekdoalei?lang=vv"
        result = get_document_webpage_uri(data)
        self.assertEqual(expected, result)

    def test_get_document_webpage_uri_returns_uri_without_format_and_without_lang(self):
        data = {
            "acron": "abcdef", "doc_id": "klamciekdoalei",
        }
        expected = "/j/abcdef/a/klamciekdoalei"
        result = get_document_webpage_uri(data)
        self.assertEqual(expected, result)


class TestGetDocumentWebpageUriList(TestCase):

    def test_get_document_webpage_uri_list_returns_uri_data_list_using_new_pattern(self):
        doc_id = "ldld"
        doc_data_list = [
            {"lang": "en", "format": "html", "pid_v2": "pid-v2",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "en", "format": "pdf", "pid_v2": "pid-v2",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "es", "format": "html", "pid_v2": "pid-v2",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "es", "format": "pdf", "pid_v2": "pid-v2",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
        ]
        expected = [
            {
                "lang": "en",
                "format": "html",
                "pid_v2": "pid-v2", "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "ldld",
                "uri": "/j/xjk/a/ldld?format=html&lang=en",
            },
            {
                "lang": "en",
                "format": "pdf",
                "pid_v2": "pid-v2", "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "ldld",
                "uri": "/j/xjk/a/ldld?format=pdf&lang=en",
            },
            {
                "lang": "es",
                "format": "html",
                "pid_v2": "pid-v2", "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "ldld",
                "uri": "/j/xjk/a/ldld?format=html&lang=es",
            },
            {
                "lang": "es",
                "format": "pdf",
                "pid_v2": "pid-v2", "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "ldld",
                "uri": "/j/xjk/a/ldld?format=pdf&lang=es",
            },
        ]
        result = get_document_webpage_uri_list(doc_id, doc_data_list, get_document_webpage_uri)
        self.assertEqual(expected, result)

    def test_get_document_webpage_uri_list_raises_value_error_if_acron_is_none_and_using_new_uri_pattern(self):
        doc_id = "ldld"
        with self.assertRaises(ValueError):
            get_document_webpage_uri_list(doc_id, [], get_document_webpage_uri)

    def test_get_document_webpage_uri_list_raises_value_error_if_acron_is_empty_str_and_using_new_uri_pattern(self):
        doc_id = "ldld"
        with self.assertRaises(ValueError):
            get_document_webpage_uri_list(doc_id, [], get_document_webpage_uri)

    def test_get_document_webpage_uri_list_returns_uri_data_list_using_classic_pattern(self):
        doc_id = "S1234-56782000123412313"
        doc_data_list = [
            {"lang": "en", "format": "html",
             "pid_v2": "S1234-56782000123412313",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "en", "format": "pdf",
             "pid_v2": "S1234-56782000123412313",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "es", "format": "html",
             "pid_v2": "S1234-56782000123412313",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
            {"lang": "es", "format": "pdf",
             "pid_v2": "S1234-56782000123412313",
             "acron": "xjk", "doc_id_for_human": "artigo-1234"},
        ]
        expected = [
            {
                "lang": "en",
                "format": "html",
                "pid_v2": "S1234-56782000123412313",
                "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "S1234-56782000123412313",
                "uri": "/scielo.php?script=sci_arttext&pid=S1234-56782000123412313&tlng=en",
            },
            {
                "lang": "en",
                "format": "pdf",
                "pid_v2": "S1234-56782000123412313",
                "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "S1234-56782000123412313",
                "uri": "/scielo.php?script=sci_pdf&pid=S1234-56782000123412313&tlng=en",
            },
            {
                "lang": "es",
                "format": "html",
                "pid_v2": "S1234-56782000123412313",
                "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "S1234-56782000123412313",
                "uri": "/scielo.php?script=sci_arttext&pid=S1234-56782000123412313&tlng=es",
            },
            {
                "lang": "es",
                "format": "pdf",
                "pid_v2": "S1234-56782000123412313",
                "acron": "xjk",
                "doc_id_for_human": "artigo-1234",
                "doc_id": "S1234-56782000123412313",
                "uri": "/scielo.php?script=sci_pdf&pid=S1234-56782000123412313&tlng=es",
            },
        ]
        result = get_document_webpage_uri_list(doc_id, doc_data_list)
        self.assertEqual(expected, result)

