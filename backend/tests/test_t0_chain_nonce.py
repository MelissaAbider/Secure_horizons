"""chain.send retries with a fresh nonce when another machine used the same key. No network."""
import pytest

from backend import chain


class FakeEth:
    def __init__(self, failures):
        self.failures, self.nonces, self.sent = list(failures), iter(range(5, 20)), []

    def get_transaction_count(self, address, block):
        return next(self.nonces)

    def estimate_gas(self, tx):
        return 100

    def send_raw_transaction(self, raw):
        self.sent.append(raw)
        if self.failures:
            raise ValueError(self.failures.pop(0))
        return b"\x01" * 32

    def wait_for_transaction_receipt(self, tx_hash, timeout):
        return {"status": 1, "blockNumber": 7, "gasUsed": 21000}


class Fn:
    def build_transaction(self, tx):
        return dict(tx)


class Sender:
    address = "0x" + "11" * 20

    def sign_transaction(self, tx):
        return type("S", (), {"raw_transaction": tx["nonce"]})()


def install(monkeypatch, failures):
    eth = FakeEth(failures)
    monkeypatch.setattr(chain, "w3", lambda: type("W", (), {"eth": eth})())
    monkeypatch.setattr(chain.time, "sleep", lambda s: None)
    return eth


def test_retries_on_nonce_clash(monkeypatch):
    eth = install(monkeypatch, ["{'code': -32000, 'message': 'nonce too low: next nonce 6, tx nonce 5'}"])
    assert chain.send(Fn(), Sender())["status"] == 1
    assert eth.sent == [5, 6]


def test_other_errors_are_not_retried(monkeypatch):
    eth = install(monkeypatch, ["execution reverted"])
    with pytest.raises(ValueError):
        chain.send(Fn(), Sender())
    assert eth.sent == [5]


def test_gives_up_after_the_retries(monkeypatch):
    eth = install(monkeypatch, ["already known"] * 10)
    with pytest.raises(ValueError):
        chain.send(Fn(), Sender())
    assert len(eth.sent) == chain.NONCE_RETRIES
