# Hybrid-Edge Media Orchestration Pipeline

**Author:** mpkumar1947

## Overview
This project implements a zero-trust, distributed data transfer pipeline designed to bridge remote cloud infrastructure with a local edge node. The system utilizes an event-driven architecture to coordinate media procurement and delivery via secure webhooks and reverse-tunnel synchronization.

## Hardware Constraints and Architecture
The system is engineered specifically for highly constrained environments, such as the Azure B1s instance (1 vCPU, 1 GiB RAM). Traditional containerization was bypassed to eliminate Docker bridge networking overhead and preserve system memory for disk I/O operations. 

Key engineering decisions for resource management include:
* **Native Integration:** All components run as native Linux systemd services to minimize the process footprint.
* **Memory Management:** Automated 4GB swap provisioning to prevent Out-of-Memory (OOM) failures during heavy multi-threaded I/O.
* **Process Isolation:** Strict application-level queue limits ensure that the Flask control plane remains responsive during high-bandwidth rsync operations.

## Security and Zero-Trust
The control plane is hardened through a zero-trust model:
* **Authentication:** All requests to the control API are validated using Telegram HMAC-SHA256 signatures, ensuring only authorized user data from the Telegram Mini App can trigger system actions.
* **Network Integrity:** A reverse Cloudflare Tunnel is utilized to expose the API and dashboard. This allows for full system management and secure rsync transfers without exposing public SSH ports or requiring inbound firewall rules on the edge node.

## Infrastructure as Code (IaC)
The repository includes a comprehensive `vps_setup.sh` script to ensure reproducible deployments. This script automates the full stack initialization, including swap configuration, qBittorrent-nox daemon setup, directory architecture, and systemd service generation.

## Configuration
See `.env.example` for required environment variables. Secrets must be stored in a local `.env` file and are excluded from source control.
