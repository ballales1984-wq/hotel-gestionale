"""Tests for monitoring configuration files (Prometheus, Alertmanager, rules)."""
import pytest
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent  # backend/.. = project root


def load_yaml(path: Path):
    """Load YAML file and return dict, or raise."""
    content = path.read_text()
    return yaml.safe_load(content)


class TestPrometheusConfig:
    """Validate prometheus.yml configuration."""

    def test_file_exists(self):
        path = PROJECT_ROOT / 'monitoring' / 'prometheus.yml'
        assert path.exists(), "prometheus.yml missing"

    def test_config_structure(self):
        path = PROJECT_ROOT / 'monitoring' / 'prometheus.yml'
        cfg = load_yaml(path)

        assert 'global' in cfg
        assert 'scrape_configs' in cfg
        assert isinstance(cfg['scrape_configs'], list)

    def test_required_jobs_present(self):
        path = PROJECT_ROOT / 'monitoring' / 'prometheus.yml'
        cfg = load_yaml(path)
        job_names = [job.get('job_name') for job in cfg['scrape_configs']]
        assert 'prometheus' in job_names
        assert 'fastapi' in job_names

    def test_fastapi_job_config(self):
        path = PROJECT_ROOT / 'monitoring' / 'prometheus.yml'
        cfg = load_yaml(path)
        fastapi_job = next((j for j in cfg['scrape_configs'] if j.get('job_name') == 'fastapi'), None)
        assert fastapi_job is not None
        assert fastapi_job.get('metrics_path') == '/metrics'
        # static_configs should include backend:8000
        static = fastapi_job.get('static_configs', [])
        assert any('backend:8000' in str(target.get('targets', [])) for target in static)


class TestAlertmanagerConfig:
    """Validate alertmanager.yml configuration."""

    def test_file_exists(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        assert path.exists(), "alertmanager.yml missing"

    def test_config_structure(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        cfg = load_yaml(path)
        assert 'route' in cfg
        assert 'receivers' in cfg
        assert isinstance(cfg['receivers'], list)

    def test_default_receiver_exists(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        cfg = load_yaml(path)
        route = cfg.get('route', {})
        assert route.get('receiver') == 'default'

    def test_receivers_defined(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        cfg = load_yaml(path)
        receiver_names = [r.get('name') for r in cfg['receivers']]
        assert 'default' in receiver_names
        assert 'critical' in receiver_names
        assert 'warning' in receiver_names
        assert 'slack' in receiver_names

    def test_slack_receiver_has_webhook_placeholder(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        cfg = load_yaml(path)
        slack_rec = next((r for r in cfg['receivers'] if r.get('name') == 'slack'), None)
        assert slack_rec is not None
        slack_cfg = slack_rec.get('slack_configs', [])
        assert len(slack_cfg) >= 1
        assert 'api_url' in slack_cfg[0]
        # Should reference env var ${SLACK_WEBHOOK_URL}
        assert '${SLACK_WEBHOOK_URL}' in slack_cfg[0]['api_url']

    def test_email_receivers_have_required_fields(self):
        path = PROJECT_ROOT / 'monitoring' / 'alertmanager.yml'
        cfg = load_yaml(path)
        for receiver in cfg['receivers']:
            if 'email_configs' in receiver:
                for email_cfg in receiver['email_configs']:
                    assert 'to' in email_cfg
                    assert 'subject' in email_cfg or 'html' in email_cfg


class TestAlertRules:
    """Validate alert.rules.yml."""

    def test_file_exists(self):
        path = PROJECT_ROOT / 'monitoring' / 'alert.rules.yml'
        assert path.exists(), "alert.rules.yml missing"

    def test_config_structure(self):
        path = PROJECT_ROOT / 'monitoring' / 'alert.rules.yml'
        cfg = load_yaml(path)
        assert 'groups' in cfg
        assert isinstance(cfg['groups'], list)
        for group in cfg['groups']:
            assert 'name' in group
            assert 'rules' in group
            assert isinstance(group['rules'], list)

    def test_rules_have_required_fields(self):
        path = PROJECT_ROOT / 'monitoring' / 'alert.rules.yml'
        cfg = load_yaml(path)
        for group in cfg['groups']:
            for rule in group['rules']:
                assert 'alert' in rule, f"Rule missing 'alert' in group {group['name']}"
                assert 'expr' in rule, f"Rule missing 'expr' in group {group['name']}"
                assert 'for' in rule, f"Rule missing 'for' in group {group['name']}"
                assert 'labels' in rule, f"Rule missing 'labels' in group {group['name']}"
                assert 'severity' in rule['labels'], f"Rule missing severity label in {rule['alert']}"

    def test_severity_labels_valid(self):
        valid_severities = {'critical', 'warning', 'info'}
        path = PROJECT_ROOT / 'monitoring' / 'alert.rules.yml'
        cfg = load_yaml(path)
        for group in cfg['groups']:
            for rule in group['rules']:
                sev = rule['labels'].get('severity')
                assert sev in valid_severities, f"Invalid severity '{sev}' in alert {rule['alert']}"

    def test_no_duplicate_alert_names(self):
        path = PROJECT_ROOT / 'monitoring' / 'alert.rules.yml'
        cfg = load_yaml(path)
        seen = set()
        for group in cfg['groups']:
            for rule in group['rules']:
                name = rule['alert']
                assert name not in seen, f"Duplicate alert name: {name}"
                seen.add(name)
