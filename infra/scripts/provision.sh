#!/usr/bin/env bash
#
# One-time provisioning for a fresh EC2 box (Ubuntu or Amazon Linux).
# Installs Docker, adds 4 GB swap (critical on a 2 GB t3.small), and creates the
# app directory. Safe to re-run (idempotent).
#
#   ssh -i key.pem user@host 'bash -s' < infra/scripts/provision.sh

set -euo pipefail

echo "▶ Provisioning Stampn host..."

# ── Swap (4 GB) ───────────────────────────────────────────────────────────────
if ! sudo swapon --show | grep -q '/swapfile'; then
  echo "▶ Creating 4 GB swap"
  sudo fallocate -l 4G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  sudo sysctl -w vm.swappiness=10 >/dev/null
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf >/dev/null
else
  echo "✓ swap already present"
fi

# ── Docker + compose plugin ───────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "▶ Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  sudo systemctl enable --now docker
else
  echo "✓ docker already installed"
fi

# ── AWS CLI ───────────────────────────────────────────────────────────────────
# backup.sh hard-fails without this when BACKUP_S3 is set. On EC2 it came free
# with the AMI, so provisioning never installed it — on any other host it is
# missing and the nightly off-box copy dies.
if ! command -v aws >/dev/null 2>&1; then
  echo "▶ Installing AWS CLI v2"
  TMP=$(mktemp -d)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "$TMP/awscliv2.zip"
  sudo apt-get install -y unzip >/dev/null 2>&1 || true
  unzip -q "$TMP/awscliv2.zip" -d "$TMP"
  sudo "$TMP/aws/install"
  rm -rf "$TMP"
else
  echo "✓ aws cli already installed"
fi

# ── App directories ───────────────────────────────────────────────────────────
# secrets/ holds wallet certs (Phase 1.1), mounted read-only into the containers.
sudo mkdir -p /opt/stampn/infra /opt/stampn/backups /opt/stampn/secrets
sudo chown -R "$USER" /opt/stampn
chmod 700 /opt/stampn/secrets

echo "✓ Provisioning complete."
echo "  Next: place infra/.env at /opt/stampn/infra/.env, then deploy."
echo "  NOTE: log out/in once so the docker group applies to your shell."
