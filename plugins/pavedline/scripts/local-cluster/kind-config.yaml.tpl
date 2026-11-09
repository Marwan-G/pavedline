# Rendered by up.sh: @KIND_NODE_IMAGE@ is replaced from versions.env.
# Host 8080 maps to NodePort 30080 on the node: the shared Gateway's Envoy proxy Service is a NodePort with that
# fixed port (HTTP only; step 12 adds TLS) (templates/infra/k8s/addons/gateway/envoyproxy.yaml).
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
      - containerPort: 30080
        hostPort: 8080
        listenAddress: "127.0.0.1"
        protocol: TCP
