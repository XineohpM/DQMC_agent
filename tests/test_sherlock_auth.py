import subprocess
import time

from dqmc_tools import sherlock_auth


def test_classify_permission_denied_as_auth_required():
    assert (
        sherlock_auth.classify_ssh_auth_failure(
            "Permission denied, please try again.\n"
            "phoenixm@login.sherlock.stanford.edu: "
            "Permission denied (gssapi-with-mic,password).\n"
        )
        == "auth_required"
    )


def test_run_preflight_uses_batchmode_and_connect_timeout(monkeypatch, tmp_path):
    krb5_conf = tmp_path / "krb5.conf"
    krb5_conf.write_text("[libdefaults]\n", encoding="utf-8")
    captured = {}

    monkeypatch.setattr("dqmc_tools.sherlock_auth.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("dqmc_tools.sherlock_auth.subprocess.run", fake_run)

    result = sherlock_auth.run_preflight(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        timeout_seconds=8,
        krb5_config_path=str(krb5_conf),
    )

    assert result == {
        "ok": True,
        "status": "ok",
        "message": "Sherlock SSH preflight succeeded.",
        "details": {"host": "sherlock", "krb5_config_path": str(krb5_conf)},
    }
    assert captured["args"] == [
        "/usr/bin/ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "sherlock",
        "true",
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["check"] is False
    assert captured["kwargs"]["timeout"] == 10
    assert captured["kwargs"]["shell"] is False


def test_run_preflight_reports_missing_krb5_config(tmp_path):
    missing = tmp_path / "missing-krb5.conf"

    result = sherlock_auth.run_preflight(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        timeout_seconds=8,
        krb5_config_path=str(missing),
    )

    assert result == {
        "ok": False,
        "status": "krb5_config_missing",
        "message": "Stanford Kerberos config is not readable.",
        "details": {
            "host": "sherlock",
            "krb5_config_path": str(missing),
            "recovery": [
                "sudo curl -o /etc/krb5.conf https://web.stanford.edu/dept/its/support/kerberos/dist/krb5.conf",
                "kinit phoenixm@stanford.edu",
                "ssh sherlock hostname",
            ],
        },
    }


def test_run_preflight_reports_auth_required(monkeypatch, tmp_path):
    krb5_conf = tmp_path / "krb5.conf"
    krb5_conf.write_text("[libdefaults]\n", encoding="utf-8")

    monkeypatch.setattr("dqmc_tools.sherlock_auth.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=255,
            stdout="",
            stderr=(
                "Permission denied, please try again.\n"
                "phoenixm@login.sherlock.stanford.edu: "
                "Permission denied (gssapi-with-mic,password).\n"
            ),
        )

    monkeypatch.setattr("dqmc_tools.sherlock_auth.subprocess.run", fake_run)

    result = sherlock_auth.run_preflight(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        timeout_seconds=8,
        krb5_config_path=str(krb5_conf),
    )

    assert result["ok"] is False
    assert result["status"] == "auth_required"
    assert result["details"]["returncode"] == 255
    assert result["details"]["recovery"] == [
        "kinit phoenixm@stanford.edu",
        "ssh sherlock hostname",
    ]


def test_start_keepalive_runs_noninteractive_checks_until_stop(monkeypatch, tmp_path):
    krb5_conf = tmp_path / "krb5.conf"
    krb5_conf.write_text("[libdefaults]\n", encoding="utf-8")
    calls = []

    def fake_run_preflight(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "status": "ok", "message": "ok", "details": {}}

    monkeypatch.setattr("dqmc_tools.sherlock_auth.run_preflight", fake_run_preflight)

    handle = sherlock_auth.start_keepalive(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        interval_seconds=0.01,
        timeout_seconds=8,
        krb5_config_path=str(krb5_conf),
    )

    assert handle is not None
    assert handle.stop_event.wait(0.05) is False
    handle.stop()
    handle.thread.join(timeout=1)

    assert calls
    assert all(call["remote_host"] == "sherlock" for call in calls)
    assert all(call["timeout_seconds"] == 8 for call in calls)
    assert all(call["krb5_config_path"] == str(krb5_conf) for call in calls)


def test_start_monitor_from_env_does_not_block_on_startup_preflight(monkeypatch, tmp_path):
    krb5_conf = tmp_path / "krb5.conf"
    krb5_conf.write_text("[libdefaults]\n", encoding="utf-8")
    calls = []

    monkeypatch.setenv("DQMC_SHERLOCK_REMOTE_HOST", "sherlock")
    monkeypatch.setenv("DQMC_SHERLOCK_ALLOWED_HOSTS", "sherlock")
    monkeypatch.setenv("DQMC_SHERLOCK_PREFLIGHT", "warn")
    monkeypatch.setenv("DQMC_SHERLOCK_KEEPALIVE_SECONDS", "100")
    monkeypatch.setenv("DQMC_SHERLOCK_KRB5_CONFIG", str(krb5_conf))

    def fake_run_preflight(**kwargs):
        calls.append(kwargs)
        time.sleep(1)
        return {"ok": True, "status": "ok", "message": "ok", "details": {}}

    monkeypatch.setattr("dqmc_tools.sherlock_auth.run_preflight", fake_run_preflight)

    started_at = time.monotonic()
    handle = sherlock_auth.start_monitor_from_env()
    elapsed = time.monotonic() - started_at

    assert handle is not None
    handle.stop()
    handle.thread.join(timeout=2)
    assert elapsed < 0.2
    assert calls
