from regions_recon_lambda.utils.api_helpers import (
    url_token_checker
)
def test_url_token_checker_none():
    url = "https://iamafunurl.com/mooooo?boo=moo"
    token = None
    result = url_token_checker(url, token)
    assert result == url


def test_url_token_checker_hastoken():
    url = "https://iamafunurl.com/mooooo?boo=moo"
    token = "super_fun_arcade_token"
    expected_result = "https://iamafunurl.com/mooooo?boo=moo&nextToken=super_fun_arcade_token"
    result = url_token_checker(url, token)
    assert result == expected_result