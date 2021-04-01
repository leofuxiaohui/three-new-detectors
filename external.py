import ssl
import socket
def get_issuer_for_endpoint(url, port,issuers):
    s = socket.socket()
    s.settimeout(TIMEOUT)
    s.connect((url, port))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cert = ctx.wrap_socket(s, server_hostname=url).getpeercert(True)
    pem = bytes(ssl.DER_cert_to_PEM_cert(cert), 'utf-8')
    issuers.add(get_issuer_from_x509(pem))


def get_issuers_for_endpoints(urls):
    issuers = set()
    for endpoint in urls:
        thread = threading.Thread(target=get_issuer_for_endpoint, args=(endpoint, 443, issuers))
        thread.start()
