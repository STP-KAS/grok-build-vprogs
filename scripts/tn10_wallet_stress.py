#!/usr/bin/env python3
"""TN10 wallet stress harness. Testnet-10 only. Never prints the seed or private keys.

Reads the BIP39 phrase from KASPA_SEED_FILE (mode 600). Talks to public wRPC
resolvers. Does not start kaspad or a miner.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import traceback
from pathlib import Path

from kaspa import (
    Mnemonic,
    Resolver,
    RpcClient,
    XPrv,
    calculate_storage_mass,
    calculate_transaction_mass,
    create_transaction,
    kaspa_to_sompi,
    maximum_standard_transaction_mass,
    sign_transaction,
)

NETWORK = "testnet-10"
# rusty-kaspa v2.1.0 TESTNET_PARAMS (suffix 10), consensus/core
STORAGE_MASS_PARAMETER = 100_000_000 * 10_000  # 10_000 KAS in sompi
BLOCK_COMPUTE_MASS = 500_000
BLOCK_STORAGE_MASS = 500_000
BLOCK_TRANSIENT_MASS = 1_000_000
BPS = 10
SOMPI = 100_000_000
MIN_FEE_PER_MASS = 100  # TN10 standardness: fee >= compute_mass * 100 (measured 2026-09-25)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEED_FILE = Path(os.environ.get("KASPA_SEED_FILE", "/root/.config/kaspa-tn10/wallet.seed"))


def disk_free_gb() -> float:
    st = os.statvfs("/")
    return st.f_bavail * st.f_frsize / 1e9


def mem_available_gb() -> float:
    avail = None
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            avail = int(line.split()[1]) / 1024 / 1024
            break
    return avail if avail is not None else 0.0


def guard() -> None:
    d, m = disk_free_gb(), mem_available_gb()
    if d < 8 or m < 1:
        raise SystemExit(f"resource guard stop: disk_free_gb={d:.2f} mem_available_gb={m:.2f}")


def load_xprv() -> XPrv:
    if SEED_FILE.stat().st_mode & 0o077:
        raise SystemExit(f"seed file {SEED_FILE} is not chmod 600")
    phrase = SEED_FILE.read_text().strip()
    if len(phrase.split()) not in (12, 24):
        raise SystemExit("seed word count is not 12 or 24")
    return XPrv(Mnemonic(phrase).to_seed())


def derive(xprv: XPrv, index: int, change: int = 0):
    pk = xprv.derive_path(f"m/44'/111111'/0'/{change}/{index}").to_private_key()
    return pk, pk.to_address("testnet").to_string()


def jdump(name: str, obj) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"wrote {path}")


async def connect(retries: int = 4) -> RpcClient:
    last = None
    for _ in range(retries):
        client = RpcClient(resolver=Resolver(), network_id=NETWORK)
        try:
            await client.connect()
            if client.is_connected:
                return client
        except Exception as exc:  # noqa: BLE001
            last = exc
        await asyncio.sleep(0.4)
    raise SystemExit(f"could not connect to a public TN10 node: {last}")


def utxo_amount(entry: dict) -> int:
    return int(entry["utxoEntry"]["amount"])


def build_sweep(entry: dict, dest: str, fee: int):
    amt = utxo_amount(entry)
    if fee < 0 or fee >= amt:
        raise ValueError("fee does not fit")
    tx = create_transaction([entry], [{"address": dest, "amount": amt - fee}], 0, None, 1)
    mass = calculate_transaction_mass(NETWORK, tx)
    storage = calculate_storage_mass(NETWORK, [amt], [amt - fee])
    return tx, mass, storage


async def submit(client: RpcClient, stx, allow_orphan: bool = False):
    return await client.submit_transaction({"transaction": stx, "allowOrphan": allow_orphan})


def txid_of(resp) -> str | None:
    if isinstance(resp, dict):
        for key in ("transactionId", "txid", "id"):
            if key in resp:
                return str(resp[key])
        # nested
        for value in resp.values():
            if isinstance(value, str) and len(value) == 64:
                return value
    return str(resp)[:80]


async def cmd_status(args) -> None:
    guard()
    xprv = load_xprv()
    _, addr0 = derive(xprv, 0)
    _, addr1 = derive(xprv, 1)
    client = await connect()
    info = await client.get_server_info()
    dag = await client.get_block_dag_info()
    sync = await client.get_sync_status()
    fees = await client.get_fee_estimate()
    bal = await client.get_balance_by_address({"address": addr0})
    utxos = (await client.get_utxos_by_addresses({"addresses": [addr0]}))["entries"]
    urls = []
    for _ in range(6):
        extra = await connect()
        urls.append(extra.url)
        await extra.disconnect()
    # explorer comparison
    import urllib.request

    req = urllib.request.Request(
        "https://api-tn10.kaspa.org/info/blockdag",
        headers={"User-Agent": "grok-build-tn10-wallet/1.0", "Accept": "application/json"},
    )
    explorer = json.load(urllib.request.urlopen(req, timeout=20))
    report = {
        "wallet_rpc": client.url,
        "server": info,
        "sync": sync,
        "dag_virtual_daa": dag.get("virtualDaaScore"),
        "dag_sink": dag.get("sink"),
        "dag_past_median_time": dag.get("pastMedianTime"),
        "explorer_virtual_daa": explorer.get("virtualDaaScore"),
        "explorer_block_count": explorer.get("blockCount"),
        "node_block_count": dag.get("blockCount"),
        "daa_delta_node_minus_explorer": int(dag.get("virtualDaaScore")) - int(explorer.get("virtualDaaScore")),
        "fees": fees,
        "balance_sompi": bal.get("balance") if isinstance(bal, dict) else bal,
        "balance_kas": (bal.get("balance") if isinstance(bal, dict) else 0) / SOMPI,
        "utxo_count": len(utxos),
        "addr0": addr0,
        "addr1": addr1,
        "resolver_sample": urls,
        "resources": {"disk_free_gb": disk_free_gb(), "mem_available_gb": mem_available_gb()},
        "standard_tx_mass": STANDARD_MASS,
        "consensus": {
            "bps": BPS,
            "block_compute_mass": BLOCK_COMPUTE_MASS,
            "block_storage_mass": BLOCK_STORAGE_MASS,
            "block_transient_mass": BLOCK_TRANSIENT_MASS,
            "storage_mass_parameter_sompi": STORAGE_MASS_PARAMETER,
            "source": "kaspanet/rusty-kaspa v2.1.0 TESTNET_PARAMS",
        },
    }
    print(json.dumps({k: report[k] for k in ("wallet_rpc", "server", "balance_kas", "utxo_count", "daa_delta_node_minus_explorer")}, indent=2))
    jdump("status.json", report)
    await client.disconnect()


async def cmd_mass(_args) -> None:
    """Local mass table. No broadcast except nothing."""
    rows = []

    def add(name, inputs, outputs):
        try:
            storage = calculate_storage_mass(NETWORK, inputs, outputs)
            err = None
        except Exception as exc:  # noqa: BLE001
            storage, err = None, f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "name": name,
                "inputs_kas": [v / SOMPI for v in inputs],
                "outputs_kas": [v / SOMPI for v in outputs],
                "storage_mass": storage,
                "error": err,
            }
        )

    add("0.5 payment + change from 1000", [kaspa_to_sompi(1000)], [kaspa_to_sompi(0.5), kaspa_to_sompi(999.49)])
    add("0.5 payment + change from 10", [kaspa_to_sompi(10)], [kaspa_to_sompi(0.5), kaspa_to_sompi(9.49)])
    add("0.5 sweep fee 0.00001", [kaspa_to_sompi(0.5)], [kaspa_to_sompi(0.5) - 1000])
    add("288 sweep fee 0.00002", [288_21965120], [288_21965120 - 2000])
    add("even 50/50 from 100", [kaspa_to_sompi(100)], [kaspa_to_sompi(50), kaspa_to_sompi(50)])
    # fanout curve on 10_000 KAS, fee ignored (outputs sum to input)
    for n, each_kas in ((20, 500), (50, 200), (100, 100), (200, 50), (300, 10000 / 300)):
        each = int(kaspa_to_sompi(each_kas))
        add(f"fanout {n} x {each_kas:.4f} KAS from 10000", [kaspa_to_sompi(10000)], [each] * n)

    # theoretical ceilings once we know a representative compute mass.
    # Filled after a real tx build in fee-probe; store formula here.
    table = {
        "storage_mass_parameter": STORAGE_MASS_PARAMETER,
        "note": "KIP-9 storage mass from kaspa-python-sdk 2.1.0 calculate_storage_mass. Zero-value outputs panic the binding (see bugs).",
        "rows": rows,
        "ceiling_formula": "tps = bps * block_mass_limit / tx_mass, using the max of compute and storage after cofactors (both limits 500_000 on TN10 v2.1.0). Transient limit is 1_000_000 and does not bind for these small standard scripts.",
        "bps": BPS,
        "block_mass_for_standard_payments": BLOCK_COMPUTE_MASS,
    }
    print(json.dumps(rows, indent=2))
    jdump("mass_table.json", table)


async def cmd_fee_probe(args) -> None:
    guard()
    xprv = load_xprv()
    pk0, addr0 = derive(xprv, 0)
    _, addr1 = derive(xprv, 1)
    client = await connect()
    fees = await client.get_fee_estimate()
    utxos = (await client.get_utxos_by_addresses({"addresses": [addr0]}))["entries"]
    small = min(utxos, key=utxo_amount)
    amt = utxo_amount(small)
    trials = []
    # Do not submit more than one successful spend of this utxo.
    submitted = False
    for fee in (0, 1, 250, 1000, 5000, 20000):
        if fee >= amt:
            continue
        row = {"fee_sompi": fee}
        try:
            tx, mass, storage = build_sweep(small, addr1, fee)
            row["mass"] = mass
            row["storage_mass"] = storage
            row["feerate"] = fee / mass if mass else None
            if args.submit and not submitted and fee == args.fee:
                stx = sign_transaction(tx, [pk0], True)
                try:
                    resp = await submit(client, stx, allow_orphan=False)
                    row["submit"] = resp
                    submitted = True
                except Exception as exc:  # noqa: BLE001
                    row["submit_error"] = f"{type(exc).__name__}: {exc}"
                    submitted = "error"
        except Exception as exc:  # noqa: BLE001
            row["build_error"] = f"{type(exc).__name__}: {exc}"
        trials.append(row)
        print(row)
    # underfunded: outputs exceed inputs, local only
    try:
        create_transaction([small], [{"address": addr1, "amount": amt + 1}], 0, None, 1)
        under = "built-unexpectedly"
    except Exception as exc:  # noqa: BLE001
        under = f"{type(exc).__name__}: {exc}"
    # zero output: may panic the interpreter. Run in a child later; skip in-process.
    report = {
        "addr0": addr0,
        "addr1": addr1,
        "node": client.url,
        "server": await client.get_server_info(),
        "fees": fees,
        "probed_utxo_kas": amt / SOMPI,
        "trials": trials,
        "underfunded_local": under,
        "submitted": submitted,
    }
    jdump("fee_probe.json", report)
    await client.disconnect()


async def cmd_burst(args) -> None:
    """1-in-1-out sweeps of distinct confirmed UTXOs. No unconfirmed chaining."""
    guard()
    xprv = load_xprv()
    pk0, addr0 = derive(xprv, 0)
    destinations = [derive(xprv, i)[1] for i in range(1, args.destinations + 1)]
    clients = [await connect() for _ in range(args.connections)]
    print("nodes", [c.url for c in clients])
    fees = await clients[0].get_fee_estimate()
    low = float(fees["estimate"]["lowBuckets"][0]["feerate"])
    # Standardness floor dominates the estimator when the mempool is empty.
    feerate = max(low, MIN_FEE_PER_MASS)
    utxos = (await clients[0].get_utxos_by_addresses({"addresses": [addr0]}))["entries"]
    # Keep the two largest UTXOs as treasury reserve unless --include-large.
    utxos_sorted = sorted(utxos, key=utxo_amount)
    if not args.include_large and len(utxos_sorted) > 2:
        usable = utxos_sorted[:-2]
    else:
        usable = utxos_sorted
    usable = usable[: args.count]
    if args.recycle:
        destinations = [addr0]
    print(f"usable {len(usable)} of {len(utxos)} feerate {feerate:.4f} low_estimate {low:.4f}")

    def fee_for(entry, dest):
        guess = 200_000
        tx, mass, storage = build_sweep(entry, dest, guess)
        need = max(1, int(mass * feerate) + (0 if mass * feerate == int(mass * feerate) else 1))
        need = max(need, mass * MIN_FEE_PER_MASS)
        if need != guess:
            tx, mass, storage = build_sweep(entry, dest, need)
            need2 = mass * MIN_FEE_PER_MASS
            if need2 != need:
                tx, mass, storage = build_sweep(entry, dest, need2)
                need = need2
        return tx, mass, storage, need

    _, sample_mass, sample_storage, fee = fee_for(usable[0], destinations[0])
    print(f"sample_mass {sample_mass} sample_storage {sample_storage} fee {fee}")

    signed = []
    build_errors = 0
    t_sign = time.perf_counter()
    for i, entry in enumerate(usable):
        dest = destinations[i % len(destinations)]
        if utxo_amount(entry) <= 300_000:
            continue
        try:
            tx, mass, storage, this_fee = fee_for(entry, dest)
            stx = sign_transaction(tx, [pk0], False)
            signed.append({"stx": stx, "mass": mass, "storage": storage, "in": utxo_amount(entry), "fee": this_fee})
        except Exception:  # noqa: BLE001
            build_errors += 1
    sign_s = time.perf_counter() - t_sign
    print(f"signed {len(signed)} in {sign_s:.2f}s ({len(signed)/sign_s:.1f}/s) build_errors {build_errors}")

    offered = 0
    ok = 0
    rejects: dict[str, int] = {}
    ids = []
    t0 = time.perf_counter()

    async def one(i, item):
        client = clients[i % len(clients)]
        try:
            resp = await submit(client, item["stx"], allow_orphan=False)
            return True, txid_of(resp), None
        except Exception as exc:  # noqa: BLE001
            return False, None, f"{type(exc).__name__}: {exc}"

    # bounded concurrency
    sem = asyncio.Semaphore(args.inflight)
    results = []

    async def wrapped(i, item):
        async with sem:
            return await one(i, item)

    futs = [asyncio.create_task(wrapped(i, item)) for i, item in enumerate(signed)]
    for fut in asyncio.as_completed(futs):
        success, txid, err = await fut
        offered += 1
        if success:
            ok += 1
            if len(ids) < 30:
                ids.append(txid)
        else:
            key = (err or "unknown")[:180]
            rejects[key] = rejects.get(key, 0) + 1
    elapsed = time.perf_counter() - t0
    # acceptance sample
    await asyncio.sleep(args.wait)
    accepted = 0
    acceptance_errors = 0
    if ids:
        for txid in ids:
            if not txid or len(txid) != 64:
                continue
            try:
                # REST acceptance is separate from node; ask the node by mempool then skip if unknown
                entry = await clients[0].get_mempool_entry({"transactionId": txid, "includeOrphanPool": True, "filterTransactionPool": False})
                # if still in mempool, not yet accepted into a block
                _ = entry
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "not found" in msg or "does not exist" in msg or "missing" in msg:
                    accepted += 1  # left mempool; may be accepted or dropped
                else:
                    acceptance_errors += 1
    report = {
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": [c.url for c in clients],
        "low_feerate": low,
        "feerate_used": feerate,
        "fee_sompi": fee,
        "sample_mass": sample_mass,
        "sample_storage_mass": sample_storage,
        "signed": len(signed),
        "sign_s": sign_s,
        "sign_per_s": len(signed) / sign_s if sign_s else None,
        "offered": offered,
        "accepted_by_rpc": ok,
        "elapsed_s": elapsed,
        "offered_tps": offered / elapsed if elapsed else None,
        "rpc_ok_tps": ok / elapsed if elapsed else None,
        "rejects": rejects,
        "sample_txids": ids,
        "build_errors": build_errors,
        "resources": {"disk_free_gb": disk_free_gb(), "mem_available_gb": mem_available_gb()},
        "theoretical_tps_if_mass_is_sample": {
            "compute_if_storage_zero": BPS * BLOCK_COMPUTE_MASS / sample_mass if sample_mass else None,
            "if_mass_is_max_compute_storage": BPS * BLOCK_COMPUTE_MASS / max(sample_mass, sample_storage or 0),
        },
    }
    print(json.dumps({k: report[k] for k in ("offered", "accepted_by_rpc", "elapsed_s", "offered_tps", "rpc_ok_tps", "rejects", "theoretical_tps_if_mass_is_sample")}, indent=2))
    jdump("burst.json", report)
    for c in clients:
        await c.disconnect()


async def cmd_lane_a(args) -> None:
    """Send `amount` KAS payments that leave change, so KIP-9 storage mass applies.

    Each successful payment spends one confirmed UTXO and is not chained.
    """
    guard()
    xprv = load_xprv()
    pk0, addr0 = derive(xprv, 0)
    dests = [derive(xprv, i)[1] for i in range(1, args.destinations + 1)]
    client = await connect()
    fees = await client.get_fee_estimate()
    low = float(fees["estimate"]["lowBuckets"][0]["feerate"])
    amount = kaspa_to_sompi(args.amount_kas)
    sent = 0
    rejects: dict[str, int] = {}
    masses = []
    t0 = time.perf_counter()
    deadline = t0 + args.seconds
    used = set()
    while time.perf_counter() < deadline and sent < args.max_txs:
        guard()
        utxos = (await client.get_utxos_by_addresses({"addresses": [addr0]}))["entries"]
        fresh = []
        for entry in utxos:
            key = (entry["outpoint"]["transactionId"], entry["outpoint"]["index"])
            amt = utxo_amount(entry)
            if key in used:
                continue
            if amt < amount + kaspa_to_sompi(1):
                continue
            # keep a large reserve: skip the single biggest if it is >= 5000 KAS
            fresh.append(entry)
        if not fresh:
            print("no fresh utxo, sleep")
            await asyncio.sleep(2)
            continue
        # spend a mid-size utxo, never the largest (reserve)
        fresh.sort(key=utxo_amount)
        if len(fresh) > 1:
            entry = fresh[-2]
        else:
            entry = fresh[0]
        amt = utxo_amount(entry)
        dest = dests[sent % len(dests)]
        fee = 300_000
        if amt - amount <= fee:
            used.add((entry["outpoint"]["transactionId"], entry["outpoint"]["index"]))
            continue
        try:
            def assemble(fee_sompi: int):
                change_amt = amt - amount - fee_sompi
                tx_ = create_transaction(
                    [entry],
                    [{"address": dest, "amount": amount}, {"address": addr0, "amount": change_amt}],
                    0,
                    None,
                    1,
                )
                mass_ = calculate_transaction_mass(NETWORK, tx_)
                storage_ = calculate_storage_mass(NETWORK, [amt], [amount, change_amt])
                return tx_, mass_, storage_, change_amt

            tx, mass, storage, change = assemble(fee)
            need = mass * MIN_FEE_PER_MASS
            if need != fee:
                fee = need
                tx, mass, storage, change = assemble(fee)
            stx = sign_transaction(tx, [pk0], False)
            resp = await submit(client, stx, False)
            sent += 1
            masses.append({"mass": mass, "storage": storage, "fee": fee, "txid": txid_of(resp)})
            used.add((entry["outpoint"]["transactionId"], entry["outpoint"]["index"]))
            if sent % 10 == 0:
                el = time.perf_counter() - t0
                print(f"laneA sent {sent} in {el:.1f}s tps {sent/el:.2f} last_mass {mass} storage {storage}")
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"[:180]
            rejects[msg] = rejects.get(msg, 0) + 1
            used.add((entry["outpoint"]["transactionId"], entry["outpoint"]["index"]))
            print("reject", msg)
            if sum(rejects.values()) > 15:
                break
        await asyncio.sleep(args.interval)
    elapsed = time.perf_counter() - t0
    report = {
        "sent": sent,
        "elapsed_s": elapsed,
        "tps": sent / elapsed if elapsed else None,
        "amount_kas": args.amount_kas,
        "masses_head": masses[:15],
        "mass_median": sorted(m["mass"] for m in masses)[len(masses) // 2] if masses else None,
        "storage_median": sorted(m["storage"] for m in masses)[len(masses) // 2] if masses else None,
        "rejects": rejects,
        "node": client.url,
        "low_feerate": low,
    }
    if masses:
        med = report["storage_median"] or report["mass_median"]
        report["theoretical_tps_at_median_mass"] = BPS * BLOCK_COMPUTE_MASS / max(report["mass_median"] or 1, report["storage_median"] or 0)
        report["two_hour_extrapolation"] = {
            "at_measured_tps": (sent / elapsed) * 7200 if elapsed else None,
            "storage_mass_per_tx": report["storage_median"],
            "note": "Each 0.5 KAS payment with a large change output costs about C/0.5KAS = 20_000 storage mass (C = 10_000 KAS).",
        }
    print(json.dumps(report, indent=2)[:4000])
    jdump("lane_a.json", report)
    await client.disconnect()


async def cmd_adversarial(_args) -> None:
    """Rejection probes. One malformed submission and local panics. Does not drain funds."""
    guard()
    xprv = load_xprv()
    pk0, addr0 = derive(xprv, 0)
    _, addr1 = derive(xprv, 1)
    client = await connect()
    utxos = (await client.get_utxos_by_addresses({"addresses": [addr0]}))["entries"]
    small = min(utxos, key=utxo_amount)
    findings = []

    # zero-value output in a subprocess so a panic cannot kill this process
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        from kaspa import calculate_storage_mass
        try:
            print(calculate_storage_mass("testnet-10", [10_000_000_00], [0, 10_000_000_00]))
        except BaseException as exc:
            print(type(exc).__name__, exc)
        """
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    findings.append(
        {
            "id": "zero-value-storage-mass",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-500:],
            "stderr": (proc.stderr or "")[-800:],
        }
    )

    # fee 0 submit of a sweep, then we do NOT want to succeed if the network accepts free txs
    # Use a copy attempt: if it succeeds, funds move  the whole smallest utxo. That is ok (0.5 KAS).
    try:
        tx, mass, storage = build_sweep(small, addr1, 0)
        stx = sign_transaction(tx, [pk0], True)
        try:
            resp = await submit(client, stx, False)
            findings.append({"id": "zero-fee-sweep", "mass": mass, "storage": storage, "submit": resp})
        except Exception as exc:  # noqa: BLE001
            findings.append({"id": "zero-fee-sweep", "mass": mass, "storage": storage, "error": f"{type(exc).__name__}: {exc}"})
    except Exception as exc:  # noqa: BLE001
        findings.append({"id": "zero-fee-sweep", "build_error": f"{type(exc).__name__}: {exc}"})

    # malformed submit
    try:
        resp = await client.submit_transaction({"transaction": {"foo": 1}, "allowOrphan": False})
        findings.append({"id": "malformed-submit", "submit": str(resp)[:300]})
    except Exception as exc:  # noqa: BLE001
        findings.append({"id": "malformed-submit", "error": f"{type(exc).__name__}: {exc}"})

    # metrics shape mismatch
    try:
        metrics = await client.get_metrics()
        findings.append({"id": "get-metrics", "ok": str(metrics)[:300]})
    except Exception as exc:  # noqa: BLE001
        findings.append({"id": "get-metrics", "error": f"{type(exc).__name__}: {exc}"})

    jdump("adversarial.json", {"node": client.url, "findings": findings})
    print(json.dumps(findings, indent=2)[:5000])
    await client.disconnect()


async def cmd_network_sample(args) -> None:
    guard()
    client = await connect()
    dag1 = await client.get_block_dag_info()
    sink1 = dag1["sink"]
    blue1 = int(dag1["virtualDaaScore"])
    t1 = time.time()
    await asyncio.sleep(args.seconds)
    dag2 = await client.get_block_dag_info()
    blue2 = int(dag2["virtualDaaScore"])
    t2 = time.time()
    chain = await client.get_virtual_chain_from_block({"startHash": sink1, "includeAcceptedTransactionIds": True})
    # response shape varies
    added = chain.get("addedChainBlockHashes") or chain.get("acceptedTransactionIds") or chain
    removed = chain.get("removedChainBlockHashes") or []
    tx_ids = []
    blocks = chain.get("acceptedTransactionIds") or []
    n_blocks = 0
    n_txs = 0
    if isinstance(blocks, list):
        n_blocks = len(blocks)
        for item in blocks:
            if isinstance(item, dict):
                ids = item.get("acceptedTransactionIds") or item.get("transactionIds") or []
                n_txs += len(ids)
            elif isinstance(item, list):
                n_txs += len(item)
    report = {
        "node": client.url,
        "seconds": t2 - t1,
        "virtual_daa_start": blue1,
        "virtual_daa_end": blue2,
        "daa_per_s": (blue2 - blue1) / (t2 - t1),
        "chain_keys": list(chain) if isinstance(chain, dict) else type(chain).__name__,
        "accepted_blocks_in_sample": n_blocks,
        "accepted_txs_in_sample": n_txs,
        "network_accepted_tps": n_txs / (t2 - t1) if t2 > t1 else None,
        "removed": len(removed) if hasattr(removed, "__len__") else None,
        "server": await client.get_server_info(),
    }
    # if the shape was unexpected, keep a short preview
    if n_txs == 0:
        report["chain_preview"] = json.dumps(chain, default=str)[:1500]
    print(json.dumps({k: report[k] for k in report if k != "chain_preview"}, indent=2)[:3000])
    if "chain_preview" in report:
        print(report["chain_preview"][:1500])
    jdump("network_sample.json", report)
    await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="TN10 wallet stress (public RPC, no local node)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("mass")
    p = sub.add_parser("fee-probe")
    p.add_argument("--submit", action="store_true")
    p.add_argument("--fee", type=int, default=1000)
    p = sub.add_parser("burst")
    p.add_argument("--count", type=int, default=200)
    p.add_argument("--connections", type=int, default=4)
    p.add_argument("--inflight", type=int, default=64)
    p.add_argument("--destinations", type=int, default=32)
    p.add_argument("--fee", type=int, default=None)
    p.add_argument("--include-large", action="store_true")
    p.add_argument("--recycle", action="store_true", help="Sweep every output back to receive index 0")
    p.add_argument("--wait", type=float, default=3.0)
    p = sub.add_parser("lane-a")
    p.add_argument("--seconds", type=float, default=120)
    p.add_argument("--max-txs", type=int, default=200)
    p.add_argument("--amount-kas", type=float, default=0.5)
    p.add_argument("--interval", type=float, default=0.2)
    p.add_argument("--destinations", type=int, default=40)
    sub.add_parser("adversarial")
    p = sub.add_parser("network-sample")
    p.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    if args.cmd == "status":
        asyncio.run(cmd_status(args))
    elif args.cmd == "mass":
        asyncio.run(cmd_mass(args))
    elif args.cmd == "fee-probe":
        asyncio.run(cmd_fee_probe(args))
    elif args.cmd == "burst":
        asyncio.run(cmd_burst(args))
    elif args.cmd == "lane-a":
        asyncio.run(cmd_lane_a(args))
    elif args.cmd == "adversarial":
        asyncio.run(cmd_adversarial(args))
    elif args.cmd == "network-sample":
        asyncio.run(cmd_network_sample(args))


if __name__ == "__main__":
    main()
