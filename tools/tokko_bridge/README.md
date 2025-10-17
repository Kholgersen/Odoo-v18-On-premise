Tokko Broker → respond.io bridge

This small FastAPI service is designed to be triggered by an Odoo Server Action (cron) and will:
- fetch new messages from Tokko Broker
- transform and forward them to respond.io
- store a cursor in a local SQLite DB for idempotency

Quick start (on your VPS):

1. copy `.env.example` to `.env` and fill values
2. create virtualenv and install dependencies

    python3 -m venv venv
    . venv/bin/activate
    pip install -r requirements.txt

3. run locally for testing:

    export TOKKO_BRIDGE_TOKEN=supersecret_between_odoo_and_vps
    uvicorn app:app --host 127.0.0.1 --port 8001

4. Configure nginx as reverse-proxy and a systemd service (see `deploy/` examples)

Notes:
- Adjust `transform_to_respondio` to fit your respond.io payload schema.
- Consider stronger storage (Postgres) if you need high availability.

Testing locally with the mock Tokko Broker
-----------------------------------------

1. Start the mock Tokko Broker on port 8002:

    uvicorn mock_tokko:app --host 127.0.0.1 --port 8002

2. Start the bridge (point TOKKO_API_URL to the mock):

    export TOKKO_BRIDGE_TOKEN=supersecret_between_odoo_and_vps; \
    export TOKKO_API_URL=http://127.0.0.1:8002/contacts; \
    export RESPONDIO_API_URL=http://127.0.0.1:8003/contacts; \
    uvicorn app:app --host 127.0.0.1 --port 8001

3. For testing respond.io side you can run a simple httpbin or mock that prints posts on 8003, or use `nc -l` to inspect.

Curl example to trigger from Odoo (or locally):

    curl -X POST http://127.0.0.1:8001/run-sync \
      -H "Authorization: Bearer supersecret_between_odoo_and_vps" \
      -H "Content-Type: application/json" \
      -d '{"initiator":"odoo_cron"}'

Odoo Server Action snippet (paste into Server Action -> Execute Python Code):

    # read secret from system parameters
    token = env['ir.config_parameter'].sudo().get_param('tokko_bridge.token')
    url = env['ir.config_parameter'].sudo().get_param('tokko_bridge.url') or 'https://your-vps.example/run-sync'
    import requests
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r = requests.post(url, headers=headers, json={'initiator': 'odoo_cron'}, timeout=30)
    if r.status_code != 200:
        raise Exception(f"Tokko bridge failed: {r.status_code} {r.text}")

Notes on respond.io
-------------------
This bridge posts a contact object to `POST /v1/contacts` with `identifiers` array (type/value). If your respond.io workspace uses different fields or requires upsert behavior (merge by identifier), adjust `transform_to_respondio` accordingly.

Optional: configuring Odoo integration from the bridge
---------------------------------------------------
If you want the bridge (VPS) to create `crm.lead` records directly in Odoo, set the following environment variables in the service:

    ODOO_URL=https://odoo.example.com
    ODOO_DB=your_db_name
    ODOO_USERNAME=api_user
    ODOO_PASSWORD=api_password

Notes:
- The bridge will try to match existing leads by an `x_external_id` custom field, falling back to `email_from` then `phone`.
- Create the custom field `x_external_id` on `crm.lead` (Char) if you want stable mapping between Tokko IDs and Odoo leads.
- If you prefer not to give the bridge Odoo credentials, keep the default flow where Odoo's Server Action records the result and/or creates leads locally.

Diseño del flujo y contrato (Tokko Broker → VPS → Odoo + respond.io)
-----------------------------------------------------------------

Resumen
- Un job recurrente en Odoo (Scheduled Action / ir.cron) dispara una Server Action que hace POST al endpoint del bridge `/run-sync` con un token Bearer.
- El bridge (FastAPI) consulta Tokko Broker (`TOKKO_API_URL`) usando su propia API key y cursor para obtener contactos/leads nuevos.
- Por cada contacto, el bridge:
  - transforma el contacto al esquema de respond.io y lo publica en `POST /v1/contacts` usando `RESPONDIO_API_KEY`;
  - opcionalmente crea o busca un `crm.lead` en Odoo vía XML-RPC si se configuran `ODOO_*` env vars;
  - actualiza el cursor local (SQLite) para evitar reprocesos.
- El bridge devuelve un resumen JSON al invocador (Odoo) con `run_id`, `sent` y `created_leads`.

Contractos HTTP
1) Odoo → Bridge
    - Endpoint: POST /run-sync
    - Headers: Authorization: Bearer <TOKKO_BRIDGE_TOKEN>
    - Body (optional): {"initiator": "odoo_cron", "last_run": "2025-10-17T..."}
    - Success: 200 OK
      {
         "status": "completed",
         "run_id": "uuid",
         "sent": <number of contacts sent to respond.io>,
         "created_leads": [{"odoo_id": 123, "external_id": "tokko-1"}, ...]
      }
    - Errors: 4xx/5xx with meaningful message. 502 indicates Tokko Broker fetch failed, 403 invalid token, 401 missing auth.

2) Bridge → Tokko Broker
    - Endpoint: GET {TOKKO_API_URL}?cursor=<cursor>
    - Headers: Authorization: Bearer <TOKKO_API_KEY>
    - Expected response: {"data": [ ...contacts... ], "next_cursor": "..."}

3) Bridge → respond.io
    - Endpoint: POST {RESPONDIO_API_URL} (defaults to /v1/contacts)
    - Headers: Authorization: Bearer <RESPONDIO_API_KEY>
    - Body example (per-contact):
      {
         "name": "Juan Pérez",
         "external_id": "tokko-1",
         "source": "tokko",
         "identifiers": [{"type": "phone", "value": "+5491..."}, {"type":"email","value":"a@b.com"}],
         "metadata": {"tokko_id": "tokko-1"}
      }

Idempotencia y cursor
- El bridge usa un cursor (`offsets` table en SQLite) devuelto por Tokko para marcar el punto de avance.
- El cursor se actualiza sólo después de procesar los items y enviar a respond.io (y opcionalmente a Odoo).

Frecuencia
- Recomendado: cada 1–5 minutos según SLA. Ajusta la frecuencia del `ir.cron` en Odoo.

Seguridad
- TLS obligatorio en el endpoint público del bridge.
- Token Bearer entre Odoo → Bridge (`TOKKO_BRIDGE_TOKEN`) y API keys para Tokko/Respond.io.
- Opcional: whitelist de IPs o VPN entre Odoo y VPS.

Errores y reintentos
- El bridge hace retries internos para llamadas a Tokko o respond.io (configurable). Si la llamada Odoo→Bridge falla, Odoo registrará el fallo y el cron reintentará en la siguiente ejecución.

Instrucciones completas en Odoo (Server Action + Scheduled Action)
----------------------------------------------------------------

Preparación en Odoo (pasos cortos)
1. Ir a Settings → Technical → System Parameters.
    - Añadir `tokko_bridge.token` = <TOKKO_BRIDGE_TOKEN>
    - Añadir `tokko_bridge.url` = https://tu-vps.example/run-sync

2. Crear Server Action (Technical → Actions → Server Actions):
    - Name: "Trigger Tokko Bridge" 
    - Model: Choose "Settings" (o cualquier modelo técnico)
    - Action To Do: Execute Python Code
    - Code: pega el siguiente snippet

Server Action (llama al bridge y registra el resultado en `ir.logging`)

     # Server Action: trigger bridge and log result
     import requests
     token = env['ir.config_parameter'].sudo().get_param('tokko_bridge.token')
     url = env['ir.config_parameter'].sudo().get_param('tokko_bridge.url')
     headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
     resp = requests.post(url, headers=headers, json={'initiator': 'odoo_cron'}, timeout=60)
     log_vals = {
          'name': 'tokko_bridge',
          'type': 'server',
          'dbname': env.cr.dbname,
          'level': 'info' if resp.status_code == 200 else 'error',
          'message': resp.text,
          'path': 'tools/tokko_bridge',
     }
     env['ir.logging'].sudo().create(log_vals)
     if resp.status_code != 200:
          raise Exception(f"Tokko bridge failed: {resp.status_code} {resp.text}")

3. Crear Scheduled Action (Technical → Automation → Scheduled Actions):
    - Name: "Tokko Bridge Cron"
    - Model: same as Server Action
    - Action To Do: Execute a Server Action → select "Trigger Tokko Bridge"
    - Interval Number: 1 (o 5)
    - Interval Unit: Minutes
    - Active: checked

Alternativa: crear Leads en Odoo desde la Server Action (si no quieres credenciales Odoo en VPS)
- Si prefieres que Odoo cree los `crm.lead` localmente, reemplaza el código anterior por este snippet que procesa la respuesta del bridge y crea leads:

     import requests
     token = env['ir.config_parameter'].sudo().get_param('tokko_bridge.token')
     url = env['ir.config_parameter'].sudo().get_param('tokko_bridge.url')
     headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
     resp = requests.post(url, headers=headers, json={'initiator': 'odoo_cron'}, timeout=60)
     if resp.status_code != 200:
          env['ir.logging'].sudo().create({'name':'tokko_bridge','type':'server','dbname':env.cr.dbname,'level':'error','message':resp.text,'path':'tools/tokko_bridge'})
          raise Exception('Tokko bridge failed')
     data = resp.json()
     # if bridge returned created_leads, skip creating duplicates
     for c in data.get('created_leads', []):
          # created by bridge; already in Odoo
          continue
     # otherwise, bridge may not create leads; you can fetch contacts from Tokko and create leads here
     # Example: create a simple lead
     # env['crm.lead'].sudo().create({'name':'Lead from Tokko','type':'lead','email_from':'test@example.com'})

Notas sobre logging/retenciones
- Usamos `ir.logging` para dejar una traza simple. Si prefieres un modelo específico, puedes crear manualmente (UI) un objeto `tokko.import.log` con campos `run_id, status, details`.

Prácticas recomendadas
- Hacer TLS obligatorio y almacenar tokens en `ir.config_parameter` (no en código).
- Si el tráfico o concurrencia aumenta, migrar a Postgres para la persistencia del cursor.

