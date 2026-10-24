from services import ipo, keys, lottery, web3

REGISTRY = {m.NAME: m for m in (ipo, web3, lottery, keys)}
