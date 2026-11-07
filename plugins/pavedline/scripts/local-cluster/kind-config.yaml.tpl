# Rendered by up.sh: @KIND_NODE_IMAGE@ is replaced from versions.env.
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
# containerd reads per-registry settings from /etc/containerd/certs.d (hosts.toml is added by up.sh).
containerdConfigPatches:
  - |-
    [plugins."io.containerd.grpc.v1.cri".registry]
      config_path = "/etc/containerd/certs.d"
nodes:
  - role: control-plane
    image: @KIND_NODE_IMAGE@
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
        listenAddress: "127.0.0.1"
        protocol: TCP
      - containerPort: 443
        hostPort: 8443
        listenAddress: "127.0.0.1"
        protocol: TCP
