# 🐳 Portainer for Floci Studio

**Portainer** is a lightweight management UI for Docker. Inspect and control every container, image, volume and network on your host from one clean dashboard — tail logs, exec into a shell, restart stacks, and more.

It's the ideal companion to the Floci Marketplace: deploy a recipe, then watch and manage it visually in Portainer.

## ✨ Features
- **Full Docker control**: Containers, images, volumes, networks and stacks.
- **Live logs & console**: Stream logs and open an in-browser terminal.
- **Resource stats**: Real-time CPU and memory usage per container.

## 🚀 Usage in Floci Studio
When you start the Portainer recipe, you can configure:
- **HTTPS UI Port**: Host port for the Portainer web UI (default: `9443`).

### First run
1. Open **https://localhost:9443** (accept the self-signed certificate warning).
2. Create your admin user within a few minutes of first boot.
3. Select the **local** environment to manage this Docker host.

> 🔌 Portainer mounts the host Docker socket (`/var/run/docker.sock`) so it can manage every container — including the ones Floci deploys.

## 🚀 Path to AWS

**Managed service:** Amazon ECS / EKS console

Manage the very containers locally that you will run as ECS tasks or EKS pods — same images, same compose topology.

**Deploy:** Push images to ECR and define the services as an ECS task definition or EKS deployment.
