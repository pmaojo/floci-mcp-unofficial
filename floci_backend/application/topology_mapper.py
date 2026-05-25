import docker
import json
import os

class TopologyMapper:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None

    def get_network_topology(self) -> str:
        if not self.client:
            return "graph TD\n  Error[Docker daemon not available]"

        containers = self.client.containers.list()

        mermaid = ["graph TD"]
        mermaid.append("  subgraph Local Machine")

        for c in containers:
            name = c.name
            ports = c.attrs['NetworkSettings']['Ports']
            port_mappings = []
            if ports:
                for container_port, host_bindings in ports.items():
                    if host_bindings:
                        host_port = host_bindings[0].get('HostPort')
                        if host_port:
                            port_mappings.append(f"{host_port}:{container_port}")

            label = f"{name}"
            if port_mappings:
                label += f"\\nPorts: {', '.join(port_mappings)}"

            mermaid.append(f'    {name}["{label}"]')

        mermaid.append("  end")

        # Discover networks
        networks = self.client.networks.list()
        for net in networks:
            if net.name in ['bridge', 'host', 'none']:
                continue

            containers_in_net = net.attrs.get('Containers', {})
            if len(containers_in_net) > 1:
                mermaid.append(f"  subgraph Network: {net.name}")
                for container_id in containers_in_net:
                    c_name = containers_in_net[container_id]['Name']
                    mermaid.append(f'    {c_name}')
                mermaid.append("  end")

        diagram = "\n".join(mermaid)

        # Save to file for UI to render
        try:
            os.makedirs("state", exist_ok=True)
            with open("state/network_topology.md", "w") as f:
                f.write("```mermaid\n" + diagram + "\n```")
        except Exception as e:
            pass # Non-blocking if file save fails

        return diagram
