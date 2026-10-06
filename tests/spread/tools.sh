tools.setup_snapd_proxy() {
  if [ "${SNAPD_USE_PROXY:-}" != true ]; then
    return
  fi

  local SNAPD_CONFD="/etc/systemd/system/snapd.service.d"
  mkdir -p "$SNAPD_CONFD"

  cat <<EOF > ${SNAPD_CONFD}/proxy.conf
[Service]
Environment=HTTPS_PROXY="$HTTPS_PROXY" HTTP_PROXY="$HTTP_PROXY" https_proxy="$HTTPS_PROXY" http_proxy="$HTTP_PROXY" NO_PROXY="$NO_PROXY" no_proxy="$NO_PROXY"
EOF

  # Since the service config changed, restart
  systemctl daemon-reload
  systemctl restart snapd.service
}

fetch_service.setup() {
  local auth="craft:craft"
  local control_port="9999"
  local proxy_port="9988"
  local permissive="true"
  local log_file="fetch-service.log"
  local upstream_http="${http_proxy:-}"
  local upstream_https="${https_proxy:-}"
  local upstream_no_proxy="${no_proxy:-}"

  while [ "$#" -gt 0 ]; do
    if [ "$#" -lt 2 ]; then
      echo "fetch_service.setup: $1 requires a value" >&2
      return 2
    fi

    case "$1" in
      --auth)
        auth="$2"
        ;;
      --control-port)
        control_port="$2"
        ;;
      --proxy-port)
        proxy_port="$2"
        ;;
      --permissive)
        permissive="$2"
        ;;
      --log-file)
        log_file="$2"
        ;;
      --upstream-http)
        upstream_http="$2"
        ;;
      --upstream-https)
        upstream_https="$2"
        ;;
      --upstream-no-proxy)
        upstream_no_proxy="$2"
        ;;
      *)
        echo "unknown fetch_service.setup option: $1" >&2
        return 2
        ;;
    esac
    shift 2
  done

  snap install --candidate fetch-service
  snap set fetch-service \
    control.auth="$auth" \
    control.port="$control_port" \
    proxy.port="$proxy_port" \
    permissive="$permissive" \
    log.file="$log_file" \
    upstream-proxy.http="$upstream_http" \
    upstream-proxy.https="$upstream_https" \
    upstream-proxy.no-proxy="$upstream_no_proxy"
  snap start fetch-service

  local attempt
  for attempt in 1 2 3 4 5; do
    sleep 1
    if curl -f "http://localhost:${control_port}/status"; then
      return 0
    fi
  done

  echo "fetch-service did not start within 5 seconds" >&2
  return 1
}

fetch_service.create_session() {
  local session_name=""
  local host_ip=""
  local policy="permissive"
  local session_prefix
  local auth control_port proxy_port session_id token

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --session-name)
        if [ "$#" -lt 2 ]; then
          echo "fetch_service.create_session: --session-name requires a value" >&2
          return 2
        fi
        session_name="$2"
        shift 2
        ;;
      --host-ip)
        if [ "$#" -lt 2 ]; then
          echo "fetch_service.create_session: --host-ip requires a value" >&2
          return 2
        fi
        host_ip="$2"
        shift 2
        ;;
      --policy)
        if [ "$#" -lt 2 ]; then
          echo "fetch_service.create_session: --policy requires a value" >&2
          return 2
        fi
        policy="$2"
        shift 2
        ;;
      *)
        echo "unknown fetch_service.create_session option: $1" >&2
        return 2
        ;;
    esac
  done

  if [ -z "$host_ip" ]; then
    host_ip=$(ip -f inet addr show lxdbr0 | sed -En -e 's/.*inet ([0-9.]+).*/\1/p')
  fi

  session_prefix="${session_name:+${session_name}_}"
  auth=$(snap get fetch-service control.auth)
  control_port=$(snap get fetch-service control.port)
  proxy_port=$(snap get fetch-service proxy.port)

  curl -f --user "$auth" -X POST -d "{\"policy\": \"${policy}\"}" \
    "http://localhost:${control_port}/session" \
    --output "${session_prefix}session.json"

  session_id=$(jq -r .id "${session_prefix}session.json")
  token=$(jq -r .token "${session_prefix}session.json")
  echo "http://${session_id}:${token}@${host_ip}:${proxy_port}" > "${session_prefix}session_url.txt"
}

fetch_service.teardown_session() {
  local session_name=""
  local session_prefix
  local auth control_port session_id token

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --session-name)
        if [ "$#" -lt 2 ]; then
          echo "fetch_service.teardown_session: --session-name requires a value" >&2
          return 2
        fi
        session_name="$2"
        shift 2
        ;;
      *)
        echo "unknown fetch_service.teardown_session option: $1" >&2
        return 2
        ;;
    esac
  done

  session_prefix="${session_name:+${session_name}_}"
  auth=$(snap get fetch-service control.auth)
  control_port=$(snap get fetch-service control.port)
  session_id=$(jq -r .id "${session_prefix}session.json")
  token=$(jq -r .token "${session_prefix}session.json")

  curl -sf --user "$auth" -X DELETE -d "{\"token\": \"${token}\"}" \
    "http://localhost:${control_port}/session/${session_id}/token"
  curl -sf --user "$auth" "http://localhost:${control_port}/session/${session_id}" \
    | tee "${session_prefix}session_report.json"
  curl -sf --user "$auth" -X DELETE \
    "http://localhost:${control_port}/session/${session_id}"
  curl -sf --user "$auth" -X DELETE \
    "http://localhost:${control_port}/resources/${session_id}"
}
