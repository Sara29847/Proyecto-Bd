import os
from datetime import datetime, timedelta
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-demo-distribuida-2026")

# ======================= SIMULACION DE CAIDA DE NODOS Y LOGS =======================
ESTADO_NODOS = {"central": True, "bogota": True, "manizales": True, "cartagena": True}  # True = activo
LOG_EVENTOS = []


class NodoCaido(Exception):
    pass


def exigir_nodo(*nodos):
    for n in nodos:
        if not ESTADO_NODOS[n]:
            raise NodoCaido(f"Nodo '{n}' no disponible (caída simulada)")


def registrar_evento(categoria, origen, destino, detalle, modo="NORMAL"):
    entrada = {
        "hora": datetime.now().strftime("%H:%M:%S"),
        "categoria": categoria,
        "origen": origen,
        "destino": destino,
        "modo": modo,
        "detalle": detalle,
    }
    LOG_EVENTOS.insert(0, entrada)
    del LOG_EVENTOS[80:]
    print(f"[{entrada['hora']}] [{categoria}] [{modo}] {origen} -> {destino}: {detalle}")


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "tienda_distribuida")

ESTADOS_VENTA = ["PENDIENTE", "EN_PROCESO", "COMPLETADA", "ENTREGADA", "CANCELADA", "DEVUELTA"]

ROLES_CONFIG = {
    "Cliente": {
        "etiqueta": "Cliente (Tienda / E-commerce)",
        "db_user": "Cliente",
        "db_pass": "ClaveCliente2026!",
        "esquema_defecto": "bogota",
        "es_cliente": True,
        "solo_comercial": False,
        "puede_vender": False,
        "puede_actualizar_clientes": False,
        "puede_gestionar_estado_venta": False,
        "puede_ajustar_inventario": False,
        "puede_crear_producto_central": False,
        "puede_editar_producto_central": False,
        "puede_eliminar_producto_central": False,
        "puede_crear_empleado": False,
        "puede_editar_empleado": False,
        "puede_ver_clientes": False,
        "puede_ver_proveedores": False,
        "puede_ver_ventas": False,
        "puede_ver_facturas": False,
        "puede_ver_nomina": False,
        "puede_ver_auditoria": False,
    },
    "director_operaciones": {
        "etiqueta": "Director de Operaciones (Dirección Central)",
        "db_user": "director_operaciones",
        "db_pass": "ClaveDirector2026!",
        "esquema_defecto": "central",
        "es_cliente": False,
        "solo_comercial": False,
        "puede_vender": False,
        "puede_actualizar_clientes": False,
        "puede_gestionar_estado_venta": False,
        "puede_ajustar_inventario": False,
        "puede_crear_producto_central": True,
        "puede_editar_producto_central": True,
        "puede_eliminar_producto_central": True,
        "puede_crear_empleado": False,
        "puede_editar_empleado": False,
        "puede_ver_clientes": True,
        "puede_ver_proveedores": False,
        "puede_ver_ventas": False,
        "puede_ver_facturas": True,
        "puede_ver_nomina": True,
        "puede_ver_auditoria": True,
    },
    "ejecutivo_comercial": {
        "etiqueta": "Ejecutivo Comercial (E-commerce y Posventa)",
        "db_user": "ejecutivo_comercial",
        "db_pass": "ClaveComercial2026!",
        "esquema_defecto": "bogota",
        "es_cliente": False,
        "solo_comercial": True,
        "puede_vender": False,
        "puede_actualizar_clientes": True,
        "puede_gestionar_estado_venta": True,
        "puede_ajustar_inventario": False,
        "puede_crear_producto_central": False,
        "puede_editar_producto_central": False,
        "puede_eliminar_producto_central": False,
        "puede_crear_empleado": False,
        "puede_editar_empleado": False,
        "puede_ver_clientes": True,
        "puede_ver_proveedores": True,
        "puede_ver_ventas": True,
        "puede_ver_facturas": True,
        "puede_ver_nomina": False,
        "puede_ver_auditoria": False,
    },
    "jefe_bodega": {
        "etiqueta": "Jefe de Bodega (Logística e Inventario)",
        "db_user": "jefe_bodega",
        "db_pass": "ClaveBodega2026!",
        "esquema_defecto": "bogota",
        "es_cliente": False,
        "solo_comercial": False,
        "puede_vender": False,
        "puede_actualizar_clientes": False,
        "puede_gestionar_estado_venta": False,
        "puede_ajustar_inventario": True,
        "puede_crear_producto_central": False,
        "puede_editar_producto_central": False,
        "puede_eliminar_producto_central": False,
        "puede_crear_empleado": False,
        "puede_editar_empleado": False,
        "puede_ver_clientes": False,
        "puede_ver_proveedores": False,
        "puede_ver_ventas": False,
        "puede_ver_facturas": False,
        "puede_ver_nomina": False,
        "puede_ver_auditoria": False,
    },
    "analista_nomina": {
        "etiqueta": "Analista de Nómina (Talento Humano)",
        "db_user": "analista_nomina",
        "db_pass": "ClaveNomina2026!",
        "esquema_defecto": "central",
        "es_cliente": False,
        "solo_comercial": False,
        "puede_vender": False,
        "puede_actualizar_clientes": False,
        "puede_gestionar_estado_venta": False,
        "puede_ajustar_inventario": False,
        "puede_crear_producto_central": False,
        "puede_editar_producto_central": False,
        "puede_eliminar_producto_central": False,
        "puede_crear_empleado": True,
        "puede_editar_empleado": True,
        "puede_ver_clientes": False,
        "puede_ver_proveedores": False,
        "puede_ver_ventas": False,
        "puede_ver_facturas": False,
        "puede_ver_nomina": True,
        "puede_ver_auditoria": False,
    },
    "auditor_externo": {
        "etiqueta": "Auditor Externo (Auditoría y Reportes)",
        "db_user": "auditor_externo",
        "db_pass": "ClaveAuditor2026!",
        "esquema_defecto": "central",
        "es_cliente": False,
        "solo_comercial": False,
        "puede_vender": False,
        "puede_actualizar_clientes": False,
        "puede_gestionar_estado_venta": False,
        "puede_ajustar_inventario": False,
        "puede_crear_producto_central": False,
        "puede_editar_producto_central": False,
        "puede_eliminar_producto_central": False,
        "puede_crear_empleado": False,
        "puede_editar_empleado": False,
        "puede_ver_clientes": True,
        "puede_ver_proveedores": False,
        "puede_ver_ventas": False,
        "puede_ver_facturas": True,
        "puede_ver_nomina": False,
        "puede_ver_auditoria": True,
    },
}

HTML_LOGIN = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ingreso por Rol - tienda_distribuida</title>
  <style>
    body { font-family: Arial, sans-serif; background: #eef2f7; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
    .box { background: #fff; padding: 28px; border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.1); width: 430px; }
    h2 { margin-top: 0; color: #1e293b; }
    label { display: block; margin-top: 12px; font-weight: bold; font-size: 14px; }
    select, input, button { width: 100%; padding: 10px; margin-top: 6px; border-radius: 6px; border: 1px solid #cbd5e1; box-sizing: border-box; }
    button { background: #0f766e; color: #fff; border: none; font-weight: bold; cursor: pointer; margin-top: 18px; }
    button:hover { background: #115e59; }
    .error { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 6px; margin-bottom: 12px; font-size: 13px; }
  </style>
</head>
<body>
  <div class="box">
    <h2>Acceso al Sistema Distribuido</h2>
    <p style="font-size:13px;color:#475569;">Base de datos: <b>tienda_distribuida</b></p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
      <label>Selecciona el rol / usuario:</label>
      <select name="rol">
        {% for key, cfg in roles.items() %}
          <option value="{{ key }}">{{ cfg.etiqueta }}</option>
        {% endfor %}
      </select>
      <label>Contraseña del rol en PostgreSQL:</label>
      <input type="password" name="clave" placeholder="Ingresa la contraseña del rol" required>
      <button type="submit">Ingresar</button>
    </form>
  </div>
</body>
</html>
"""

HTML_PANEL = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Panel - {{ rol_cfg.etiqueta }}</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f1f5f9; margin: 0; padding: 20px; color: #1e293b; }
    .topbar { background: #0f172a; color: #fff; padding: 14px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; }
    .badge { background: #0d9488; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 16px; margin-bottom: 18px; }
    .card { background: #fff; padding: 18px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin-bottom: 18px; }
    .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 10px; }
    .field label { display: block; font-size: 12px; font-weight: bold; color: #334155; margin-bottom: 4px; }
    .field input, .field select, textarea.sql-box { width: 100%; padding: 8px; border-radius: 5px; border: 1px solid #cbd5e1; box-sizing: border-box; }
    textarea.sql-box { font-family: Consolas, Monaco, monospace; font-size: 13px; min-height: 115px; background: #0f172a; color: #e2e8f0; padding: 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
    th, td { border: 1px solid #e2e8f0; padding: 8px; text-align: left; }
    th { background: #334155; color: #fff; }
    tr.bajo-stock { background: #fef9c3; }
    button { padding: 9px 14px; border-radius: 5px; border: none; background: #2563eb; color: #fff; cursor: pointer; font-weight: bold; margin-top: 12px; }
    button:hover { background: #1d4ed8; }
    button.btn-sec { background: #0f766e; margin-top: 0; padding: 6px 10px; font-size: 12px; }
    button.btn-warn { background: #b91c1c; margin-top: 0; }
    .msg { background: #dcfce7; color: #166534; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; }
    .warn { background: #fef3c7; color: #92400e; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; border: 1px solid #f59e0b; }
    .err { background: #fee2e2; color: #991b1b; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; white-space: pre-wrap; font-size: 13px; }
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <b>tienda_distribuida</b> &mdash; Rol: <span class="badge">{{ rol_cfg.etiqueta }}</span>
    </div>
    <form method="get" action="{{ url_for('panel') }}" style="margin:0;">
      <label style="font-size:13px;">Región:
        <select name="region" onchange="this.form.submit()">
          {% for reg in ['bogota', 'manizales', 'cartagena'] %}
            <option value="{{ reg }}" {% if reg == region %}selected{% endif %}>{{ reg }}</option>
          {% endfor %}
        </select>
      </label>
    </form>
    <a href="{{ url_for('logout') }}" style="color:#f8fafc;text-decoration:none;background:#334155;padding:7px 12px;border-radius:6px;">Cerrar sesión</a>
  </div>

  <div class="card" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
    <b>Estado de nodos:</b>
    {% for n, activo in estado_nodos.items() %}
      <span class="badge" style="background:{{ '#0d9488' if activo else '#b91c1c' }}">{{ n }}: {{ 'ACTIVO' if activo else 'CAÍDO' }}</span>
      {% if puede_simular %}
      <form method="post" action="{{ url_for('cambiar_nodo', nodo=n, accion=('caer' if activo else 'levantar')) }}" style="margin:0;">
        <input type="hidden" name="region" value="{{ region }}">
        <button type="submit" class="{{ 'btn-warn' if activo else 'btn-sec' }}">{{ 'Caer' if activo else 'Levantar' }}</button>
      </form>
      {% endif %}
    {% endfor %}
  </div>

  {% if not estado_nodos[region] %}
  <div class="warn">
    <b>Partición / Contingencia en {{ region }}:</b> El nodo de <b>{{ region }}</b> figura como caído, pero <b>no te movemos a otra región</b>. Puedes seguir operando y comprando en <b>{{ region }}</b> localmente (pendiente de sincronización / conciliación con el resto de nodos).
  </div>
  {% endif %}

  {% if not estado_nodos['central'] %}
  <div class="warn">
    <b>Nodo central caído:</b> Las operaciones regionales continúan en su propia región; los cambios sobre <b>central</b> (catálogo maestro, nómina, auditoría) quedan restringidos hasta recuperar <b>central</b>.
  </div>
  {% endif %}

  {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}
  {% if err %}<div class="err">{{ err }}</div>{% endif %}

  {% if puede_simular %}
  <div class="card" id="consola-sql">
    <h3>Consola SQL de Solo Lectura (Director de Operaciones &rarr; PostgreSQL)</h3>
    <p style="font-size:13px;color:#475569;margin-top:0;">Solo se permiten consultas (<code>SELECT</code>, <code>WITH</code>, <code>EXPLAIN</code>, <code>SHOW</code>). No se permite <code>DELETE</code>, <code>INSERT</code>, <code>UPDATE</code> ni modificar la base de datos.</p>
    <form method="post" action="{{ url_for('ejecutar_sql') }}">
      <input type="hidden" name="region" value="{{ region }}">
      <textarea name="sql_query" class="sql-box" placeholder="Ej. SELECT * FROM central.producto;" required>{{ sql_query or '' }}</textarea>
      <button type="submit" style="background:#0f766e;">Ejecutar Consulta</button>
    </form>

    {% if sql_resultado %}
      <h4 style="margin-top:16px;">Resultado de la consulta ({{ sql_resultado | length }} fila(s))</h4>
      <div style="overflow-x:auto;">
        <table>
          <tr>{% for col in sql_resultado[0].keys() %}<th>{{ col }}</th>{% endfor %}</tr>
          {% for row in sql_resultado %}
            <tr>{% for val in row.values() %}<td>{{ val }}</td>{% endfor %}</tr>
          {% endfor %}
        </table>
      </div>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.es_cliente %}
  <div class="card">
    <h3>Mis Datos de Cliente ({{ region }}.cliente)</h3>
    <form method="post" action="{{ url_for('cliente_guardar_datos') }}" id="form-cliente-datos">
      <input type="hidden" name="region" value="{{ region }}">
      <div class="form-grid">
        <div class="field">
          <label>Tipo documento</label>
          <select name="tipo_documento">
            <option value="CC" {% if cliente_actual and cliente_actual.get('tipo_documento') == 'CC' %}selected{% endif %}>CC</option>
            <option value="CE" {% if cliente_actual and cliente_actual.get('tipo_documento') == 'CE' %}selected{% endif %}>CE</option>
            <option value="TI" {% if cliente_actual and cliente_actual.get('tipo_documento') == 'TI' %}selected{% endif %}>TI</option>
            <option value="NIT" {% if cliente_actual and cliente_actual.get('tipo_documento') == 'NIT' %}selected{% endif %}>NIT</option>
          </select>
        </div>
        <div class="field">
          <label>Número documento</label>
          <input type="text" name="numero_documento" inputmode="numeric" pattern="[0-9]{5,15}" minlength="5" maxlength="15" value="{{ cliente_actual.get('numero_documento', '') if cliente_actual else '' }}" placeholder="Ej. 1029384756" required>
        </div>
        <div class="field">
          <label>Nombre completo</label>
          <input type="text" name="nombre" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}" minlength="2" maxlength="100" value="{{ cliente_actual.get('nombre', '') if cliente_actual else '' }}" placeholder="Ej. Andrea Bonilla" required>
        </div>
        <div class="field">
          <label>Indicativo país</label>
          <input type="text" name="codigo_pais" value="{{ cliente_actual.get('codigo_pais', '+57') if cliente_actual else '+57' }}" maxlength="10" required>
        </div>
        <div class="field">
          <label>Teléfono</label>
          <input type="text" name="numero_telefono" inputmode="numeric" pattern="[0-9]{7,15}" minlength="7" maxlength="15" value="{{ cliente_actual.get('numero_telefono', '') if cliente_actual else '' }}" placeholder="Ej. 3001234567" required>
        </div>
        <div class="field">
          <label>Dirección de envío</label>
          <input type="text" name="direccion" value="{{ cliente_actual.get('direccion', '') if cliente_actual else '' }}" placeholder="Ej. Calle 72 # 10-34" required>
        </div>
      </div>
      <button type="submit">Guardar Mis Datos</button>
    </form>
  </div>

  <div class="card">
    <h3>Mi Carrito (Reserva temporal en {{ region }}.reserva_stock)</h3>
    {% if carrito_items %}
      {% set carrito_total = carrito_items | sum(attribute='subtotal') %}
      <table>
        <tr>
          <th>ID Reserva</th>
          <th>Producto</th>
          <th>Bodega</th>
          <th>Cantidad</th>
          <th>Precio Unit.</th>
          <th>Subtotal</th>
          <th>Expira en</th>
          <th>Acción</th>
        </tr>
        {% for item in carrito_items %}
          <tr>
            <td>#{{ item.id_reserva }}</td>
            <td>{{ item.nombre }}</td>
            <td>{{ item.id_bodega }}</td>
            <td>{{ item.cantidad }}</td>
            <td>${{ '%.2f'|format(item.precio) }}</td>
            <td>${{ '%.2f'|format(item.subtotal) }}</td>
            <td>{{ item.expira_en }}</td>
            <td>
              <form method="post" action="{{ url_for('cliente_quitar_carrito', id_reserva=item.id_reserva) }}" style="margin:0;">
                <input type="hidden" name="region" value="{{ region }}">
                <button type="submit" class="btn-warn">Quitar</button>
              </form>
            </td>
          </tr>
        {% endfor %}
        <tr>
          <td colspan="5" style="text-align:right;font-weight:bold;background:#f8fafc;">Total a pagar:</td>
          <td colspan="3" style="font-weight:bold;background:#f8fafc;color:#0f766e;">${{ '%.2f'|format(carrito_total) }}</td>
        </tr>
      </table>
      <form method="post" action="{{ url_for('cliente_confirmar_compra') }}" style="margin-top:12px;">
        <input type="hidden" name="region" value="{{ region }}">
        <p style="margin:0 0 10px;font-size:15px;font-weight:bold;">Total del carrito: ${{ '%.2f'|format(carrito_total) }}</p>
        <div class="form-grid" style="max-width:420px;">
          <div class="field">
            <label>Método de pago</label>
            <select name="metodo_pago">
              <option value="EFECTIVO">EFECTIVO</option>
              <option value="TARJETA">TARJETA</option>
              <option value="TRANSFERENCIA">TRANSFERENCIA</option>
            </select>
          </div>
        </div>
        <button type="submit" style="background:#0f766e;">Confirmar Compra</button>
      </form>
    {% else %}
      <p style="font-size:13px;color:#475569;">Tu carrito está vacío. Agrega productos desde el catálogo para reservar su stock sin confirmar la compra todavía.</p>
    {% endif %}
  </div>

  <div class="card">
    <h3>Catálogo de Productos ({{ region }})</h3>
    {% if tienda_catalogo %}
      <table>
        <tr>
          <th>ID Prod.</th>
          <th>Nombre</th>
          <th>Precio</th>
          <th>Bodega</th>
          <th>Disponible</th>
          <th>Agregar al Carrito</th>
        </tr>
        {% for p in tienda_catalogo %}
          <tr>
            <td>{{ p.id_producto }}</td>
            <td>{{ p.nombre }}</td>
            <td>${{ '%.2f'|format(p.precio) }}</td>
            <td>{{ p.id_bodega }}</td>
            <td>{{ p.disponible }}</td>
            <td>
              {% if p.disponible > 0 and p.id_inventario %}
                <form method="post" action="{{ url_for('cliente_agregar_carrito') }}" style="margin:0;display:flex;gap:8px;align-items:center;">
                  <input type="hidden" name="region" value="{{ region }}">
                  <input type="hidden" name="id_inventario" value="{{ p.id_inventario }}">
                  <input type="number" name="cantidad" value="1" min="1" max="{{ p.disponible }}" style="width:75px;margin-top:0;" required>
                  <button type="submit" class="btn-sec">Reservar</button>
                </form>
              {% else %}
                <span style="color:#b91c1c;font-weight:bold;">Sin stock disponible</span>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">No hay productos disponibles en {{ region }}.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_actualizar_clientes %}
  <div class="card">
    <h3>Soporte Comercial: Actualizar Datos de Cliente ({{ region }}.cliente)</h3>
    <p style="font-size:13px;color:#475569;margin-top:0;">Selecciona un cliente existente de {{ region }} para actualizar sus datos de envío, contacto o documento.</p>
    {% if clientes %}
      <form method="post" action="{{ url_for('comercial_actualizar_cliente') }}" id="form-comercial-cliente">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>Cliente a actualizar</label>
            <select name="id_cliente" id="select-cliente-editar" required>
              {% for cli in clientes %}
                <option value="{{ cli.id_cliente }}"
                        data-tipo="{{ cli.tipo_documento }}"
                        data-doc="{{ cli.numero_documento }}"
                        data-nombre="{{ cli.nombre }}"
                        data-pais="{{ cli.codigo_pais or '+57' }}"
                        data-tel="{{ cli.numero_telefono }}"
                        data-dir="{{ cli.direccion or '' }}">
                  #{{ cli.id_cliente }} - {{ cli.nombre }} ({{ cli.numero_documento }})
                </option>
              {% endfor %}
            </select>
          </div>
          <div class="field">
            <label>Tipo documento</label>
            <select name="tipo_documento" id="com-tipo-doc" required>
              <option value="CC">CC</option>
              <option value="CE">CE</option>
              <option value="TI">TI</option>
              <option value="NIT">NIT</option>
              <option value="PASAPORTE">PASAPORTE</option>
              <option value="DNI">DNI</option>
              <option value="RUT">RUT</option>
            </select>
          </div>
          <div class="field">
            <label>Número documento</label>
            <input type="text" name="numero_documento" id="com-num-doc" inputmode="numeric" pattern="[0-9]{5,15}" minlength="5" maxlength="15" placeholder="Ej. 1029384756" required>
          </div>
          <div class="field">
            <label>Nombre completo</label>
            <input type="text" name="nombre" id="com-nombre" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}" minlength="2" maxlength="100" placeholder="Ej. Laura Gómez" required>
          </div>
          <div class="field">
            <label>Indicativo país</label>
            <input type="text" name="codigo_pais" id="com-cod-pais" pattern="\+?[0-9]{1,4}" minlength="1" maxlength="5" value="+57" placeholder="Ej. +57" required>
          </div>
          <div class="field">
            <label>Teléfono</label>
            <input type="text" name="numero_telefono" id="com-telefono" inputmode="numeric" pattern="[0-9]{7,15}" minlength="7" maxlength="15" placeholder="Ej. 3001234567" required>
          </div>
          <div class="field">
            <label>Dirección de envío</label>
            <input type="text" name="direccion" id="com-direccion" minlength="5" maxlength="150" placeholder="Ej. Calle 72 # 10-34" required>
          </div>
        </div>
        <button type="submit" style="background:#0f766e;">Actualizar Cliente en {{ region }}</button>
      </form>
    {% else %}
      <p style="font-size:13px;color:#475569;">No hay clientes registrados en {{ region }} para actualizar.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_vender or rol_cfg.puede_ajustar_inventario %}
  <div class="grid">
    {% if rol_cfg.puede_vender %}
    <div class="card">
      <h3>Registrar Venta ({{ region }})</h3>
      <form method="post" action="{{ url_for('vender') }}">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>Cliente existente (opcional)</label>
            <select name="id_cliente_existente">
              <option value="">-- Nuevo cliente --</option>
              {% for cli in clientes_menu %}
                <option value="{{ cli.id_cliente }}">{{ cli.id_cliente }} - {{ cli.nombre }} ({{ cli.numero_documento }})</option>
              {% endfor %}
            </select>
          </div>
          <div class="field">
            <label>Nombre del cliente</label>
            <input type="text" name="cliente_nombre" placeholder="Ej. Laura Gómez">
          </div>
          <div class="field">
            <label>Tipo documento cliente</label>
            <select name="cliente_tipo_doc">
              <option value="CC">CC</option>
              <option value="CE">CE</option>
              <option value="TI">TI</option>
              <option value="NIT">NIT</option>
            </select>
          </div>
          <div class="field">
            <label>Identificación cliente</label>
            <input type="text" name="cliente_documento" placeholder="Ej. 1029384756">
          </div>
          <div class="field">
            <label>Indicativo país</label>
            <input type="text" name="codigo_pais" value="+57" maxlength="10" placeholder="Ej. +57">
          </div>
          <div class="field">
            <label>Teléfono cliente</label>
            <input type="text" name="cliente_telefono" placeholder="Ej. 3001234567">
          </div>
          <div class="field">
            <label>Dirección cliente</label>
            <input type="text" name="cliente_direccion" placeholder="Ej. Calle 72 # 10-34">
          </div>
          <div class="field">
            <label>Producto</label>
            {% if productos %}
              <select name="id_producto" required>
                {% for prod in productos %}
                  <option value="{{ prod.id_producto }}">{{ prod.id_producto }} - {{ prod.nombre }} (${{ prod.precio }})</option>
                {% endfor %}
              </select>
            {% else %}
              <input type="number" name="id_producto" placeholder="Ej. 2001" required>
            {% endif %}
          </div>
          <div class="field">
            <label>Bodega</label>
            {% if bodegas %}
              <select name="id_bodega" required>
                {% for bod in bodegas %}
                  <option value="{{ bod.id_bodega }}">{{ bod.id_bodega }} - {{ bod.nombre }}</option>
                {% endfor %}
              </select>
            {% else %}
              <input type="number" name="id_bodega" placeholder="Ej. 2001" required>
            {% endif %}
          </div>
          <div class="field">
            <label>Cantidad de productos</label>
            <input type="number" name="cantidad" value="1" min="1" required>
          </div>
          <div class="field">
            <label>Método de pago</label>
            <select name="metodo_pago">
              <option value="EFECTIVO">EFECTIVO</option>
              <option value="TARJETA">TARJETA</option>
              <option value="TRANSFERENCIA">TRANSFERENCIA</option>
            </select>
          </div>
        </div>
        <button type="submit">Guardar Venta</button>
      </form>
    </div>
    {% endif %}

    {% if rol_cfg.puede_ajustar_inventario %}
    <div class="card">
      <h3>Actualizar Inventario ({{ region }})</h3>
      <form method="post" action="{{ url_for('ajustar_stock') }}">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>ID Inventario</label>
            <input type="number" name="id_inventario" placeholder="ID Inventario" required>
          </div>
          <div class="field">
            <label>Nueva cantidad</label>
            <input type="number" name="nueva_cantidad" placeholder="Nueva cantidad" min="0" required>
          </div>
        </div>
        <button type="submit">Actualizar Stock</button>
      </form>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_crear_producto_central or rol_cfg.puede_crear_empleado %}
  <div class="grid">
    {% if rol_cfg.puede_crear_producto_central %}
    <div class="card">
      <h3>Replicación de Producto (central.producto &rarr; regiones)</h3>
      <form method="post" action="{{ url_for('crear_producto_central') }}" id="form-crear-producto">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>Nombre producto</label>
            <input type="text" name="nombre" id="prod-nombre" minlength="2" maxlength="100" placeholder="Ej. iPhone 15" required>
          </div>
          <div class="field">
            <label>ID Categoría</label>
            <input type="number" name="id_categoria" id="prod-cat" value="1" min="1" step="1" required>
          </div>
          <div class="field">
            <label>ID Proveedor</label>
            <input type="number" name="id_proveedor" id="prod-prov" value="2001" min="1" step="1" placeholder="Ej. 2001">
          </div>
          <div class="field">
            <label>Precio ($)</label>
            <input type="number" step="0.01" name="precio" id="prod-precio" value="120.00" min="0.01" required>
          </div>
          <div class="field">
            <label>Peso (kg)</label>
            <input type="number" step="0.01" name="peso" id="prod-peso" value="0.85" min="0">
          </div>
        </div>
        <button type="submit">Crear y Replicar Producto</button>
      </form>
    </div>
    {% endif %}

    {% if rol_cfg.puede_crear_empleado %}
    <div class="card">
      <h3>Alta de Empleado (Fragmentación Vertical)</h3>
      <form method="post" action="{{ url_for('crear_empleado') }}" id="form-crear-empleado">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>Nombre completo</label>
            <input type="text" name="nombre" id="emp-nombre" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}" minlength="2" maxlength="100" placeholder="Ej. Andrés Díaz" required>
          </div>
          <div class="field">
            <label>Documento</label>
            <input type="text" name="numero_documento" id="emp-doc" inputmode="numeric" pattern="[0-9]{5,15}" minlength="5" maxlength="15" placeholder="Ej. 1011223344" required>
          </div>
          <div class="field">
            <label>Teléfono</label>
            <input type="text" name="numero_telefono" id="emp-tel" inputmode="numeric" pattern="[0-9]{7,15}" minlength="7" maxlength="15" placeholder="Ej. 3112233445" required>
          </div>
          <div class="field">
            <label>Cargo (central.empleado_nomina)</label>
            <input type="text" name="cargo" id="emp-cargo" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü .\-/]{2,80}" minlength="2" maxlength="80" placeholder="Ej. Asesor Comercial" required>
          </div>
          <div class="field">
            <label>Salario ($)</label>
            <input type="number" step="0.01" name="salario" id="emp-salario" value="1800000" min="0.01" required>
          </div>
        </div>
        <button type="submit">Guardar Identificación y Nómina</button>
      </form>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_editar_producto_central or rol_cfg.puede_eliminar_producto_central %}
  <div class="grid">
    {% if rol_cfg.puede_editar_producto_central %}
    <div class="card">
      <h3>Editar Producto Central (central.producto &rarr; regiones)</h3>
      {% if productos_central_editables %}
        <form method="post" action="{{ url_for('editar_producto_central') }}" id="form-editar-producto">
          <input type="hidden" name="region" value="{{ region }}">
          <div class="form-grid">
            <div class="field">
              <label>Producto a editar</label>
              <select name="id_producto" id="edit-prod-select" required>
                {% for pr in productos_central_editables %}
                  <option value="{{ pr.id_producto }}"
                          data-nombre="{{ pr.nombre or '' }}"
                          data-cat="{{ pr.id_categoria if pr.id_categoria is not none else '' }}"
                          data-prov="{{ pr.id_proveedor if pr.id_proveedor is not none else '' }}"
                          data-precio="{{ pr.precio if pr.precio is not none else '' }}"
                          data-peso="{{ pr.peso if pr.peso is not none else '' }}"
                          data-activo="{{ 'true' if pr.activo is none or pr.activo else 'false' }}">
                    #{{ pr.id_producto }} - {{ pr.nombre }} (${{ pr.precio }})
                  </option>
                {% endfor %}
              </select>
            </div>
            <div class="field">
              <label>Nombre producto</label>
              <input type="text" name="nombre" id="edit-prod-nombre" minlength="2" maxlength="100" placeholder="Ej. iPhone 15" required>
            </div>
            <div class="field">
              <label>ID Categoría</label>
              <input type="number" name="id_categoria" id="edit-prod-cat" min="1" step="1" required>
            </div>
            <div class="field">
              <label>ID Proveedor</label>
              <input type="number" name="id_proveedor" id="edit-prod-prov" min="1" step="1" placeholder="Opcional">
            </div>
            <div class="field">
              <label>Precio ($)</label>
              <input type="number" step="0.01" name="precio" id="edit-prod-precio" min="0.01" required>
            </div>
            <div class="field">
              <label>Peso (kg)</label>
              <input type="number" step="0.01" name="peso" id="edit-prod-peso" min="0" placeholder="Opcional">
            </div>
            <div class="field">
              <label>Estado</label>
              <select name="activo" id="edit-prod-activo">
                <option value="true">Activo</option>
                <option value="false">Inactivo</option>
              </select>
            </div>
          </div>
          <button type="submit" style="background:#0f766e;">Guardar Cambios del Producto</button>
        </form>
      {% else %}
        <p style="font-size:13px;color:#475569;">No hay productos disponibles en central.producto para editar.</p>
      {% endif %}
    </div>
    {% endif %}

    {% if rol_cfg.puede_eliminar_producto_central %}
    <div class="card">
      <h3>Eliminar Producto Central (central.producto)</h3>
      {% if productos_central_editables %}
        <form method="post" action="{{ url_for('eliminar_producto_central') }}" onsubmit="return confirm('¿Seguro que deseas eliminar este producto y sus registros asociados en inventario/reservas/detalle?');">
          <input type="hidden" name="region" value="{{ region }}">
          <div class="form-grid">
            <div class="field">
              <label>Producto a eliminar</label>
              <select name="id_producto" required>
                {% for pr in productos_central_editables %}
                  <option value="{{ pr.id_producto }}">#{{ pr.id_producto }} - {{ pr.nombre }} (${{ pr.precio }})</option>
                {% endfor %}
              </select>
            </div>
          </div>
          <button type="submit" class="btn-warn" style="margin-top:12px;">Eliminar Producto</button>
        </form>
      {% else %}
        <p style="font-size:13px;color:#475569;">No hay productos disponibles en central.producto para eliminar.</p>
      {% endif %}
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_editar_empleado %}
  <div class="card">
    <h3>Editar Información de Empleado ({{ region }}.empleado_identificacion y central.empleado_nomina)</h3>
    {% if empleados_editables %}
      <form method="post" action="{{ url_for('editar_empleado') }}" id="form-editar-empleado">
        <input type="hidden" name="region" value="{{ region }}">
        <div class="form-grid">
          <div class="field">
            <label>Empleado a editar</label>
            <select name="id_empleado" id="edit-emp-select" required>
              {% for e in empleados_editables %}
                <option value="{{ e.id_empleado }}"
                        data-nombre="{{ e.nombre if e.nombre and e.nombre != '—' else '' }}"
                        data-doc="{{ e.numero_documento or '' }}"
                        data-tel="{{ e.numero_telefono or '' }}"
                        data-cargo="{{ e.cargo or '' }}"
                        data-salario="{{ e.salario if e.salario is not none else '' }}">
                  #{{ e.id_empleado }} - {{ e.nombre }} ({{ e.cargo or 'Sin cargo' }})
                </option>
              {% endfor %}
            </select>
          </div>
          <div class="field">
            <label>Nombre completo</label>
            <input type="text" name="nombre" id="edit-emp-nombre" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}" minlength="2" maxlength="100" placeholder="Ej. Andrés Díaz" required>
          </div>
          <div class="field">
            <label>Documento</label>
            <input type="text" name="numero_documento" id="edit-emp-doc" inputmode="numeric" pattern="[0-9]{5,15}" minlength="5" maxlength="15" placeholder="Ej. 1011223344" required>
          </div>
          <div class="field">
            <label>Teléfono</label>
            <input type="text" name="numero_telefono" id="edit-emp-tel" inputmode="numeric" pattern="[0-9]{7,15}" minlength="7" maxlength="15" placeholder="Ej. 3112233445" required>
          </div>
          <div class="field">
            <label>Cargo (central.empleado_nomina)</label>
            <input type="text" name="cargo" id="edit-emp-cargo" pattern="[A-Za-zÁÉÍÓÚáéíóúÑñÜü .\-/]{2,80}" minlength="2" maxlength="80" placeholder="Ej. Asesor Comercial" required>
          </div>
          <div class="field">
            <label>Salario ($)</label>
            <input type="number" step="0.01" name="salario" id="edit-emp-salario" min="0.01" required>
          </div>
        </div>
        <button type="submit" style="background:#0f766e;">Guardar Cambios del Empleado</button>
      </form>
    {% else %}
      <p style="font-size:13px;color:#475569;">No hay empleados disponibles para editar.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if catalogo and not rol_cfg.es_cliente and not rol_cfg.solo_comercial %}
  <div class="card">
    <h3>Catálogo de Productos ({{ region }}.producto)</h3>
    <table>
      <tr>{% for col in catalogo[0].keys() %}<th>{{ col }}</th>{% endfor %}</tr>
      {% for p in catalogo %}<tr>{% for val in p.values() %}<td>{{ val }}</td>{% endfor %}</tr>{% endfor %}
    </table>
  </div>
  {% endif %}

  {% if inventarios and not rol_cfg.es_cliente and not rol_cfg.solo_comercial %}
  <div class="card">
    <h3>Consulta de Inventario ({{ region }}.inventario) &mdash; <span style="font-size:12px;font-weight:normal;">Filas en amarillo: cantidad &le; nivel_minimo</span></h3>
    <table>
      <tr>
        {% for col in inventarios[0].keys() %}<th>{{ col }}</th>{% endfor %}
      </tr>
      {% for r in inventarios %}
        <tr class="{% if r.get('cantidad') is not none and r.get('nivel_minimo') is not none and r['cantidad'] <= r['nivel_minimo'] %}bajo-stock{% endif %}">
          {% for val in r.values() %}<td>{{ val }}</td>{% endfor %}
        </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_clientes %}
  <div class="card">
    <h3>Consulta de Clientes ({{ region }}.cliente)</h3>
    {% if clientes %}
      <table>
        <tr>
          {% for col in clientes[0].keys() %}<th>{{ col }}</th>{% endfor %}
        </tr>
        {% for c in clientes %}
          <tr>{% for val in c.values() %}<td>{{ val }}</td>{% endfor %}</tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin clientes registrados en {{ region }}.cliente.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_ventas %}
  <div class="card">
    <h3>Pedidos Digitales / Ventas ({{ region }}.venta)</h3>
    {% if ventas %}
      <table>
        <tr>
          {% for col in ventas[0].keys() %}<th>{{ col }}</th>{% endfor %}
          {% if rol_cfg.puede_gestionar_estado_venta %}<th>Actualizar Estado</th>{% endif %}
          <th>Productos del Pedido</th>
        </tr>
        {% for v in ventas %}
          <tr>
            {% for val in v.values() %}<td>{{ val }}</td>{% endfor %}
            {% if rol_cfg.puede_gestionar_estado_venta %}
            <td>
              <form method="post" action="{{ url_for('comercial_actualizar_estado_venta') }}" style="margin:0;display:flex;gap:6px;align-items:center;">
                <input type="hidden" name="region" value="{{ region }}">
                <input type="hidden" name="id_venta" value="{{ v['id_venta'] }}">
                <select name="estado" style="padding:5px;border-radius:4px;border:1px solid #cbd5e1;font-size:12px;">
                  {% for est in estados_venta %}
                    <option value="{{ est }}" {% if v['estado'] == est %}selected{% endif %}>{{ est }}</option>
                  {% endfor %}
                  {% if v['estado'] and v['estado'] not in estados_venta %}
                    <option value="{{ v['estado'] }}" selected>{{ v['estado'] }}</option>
                  {% endif %}
                </select>
                <button type="submit" class="btn-sec">Guardar</button>
              </form>
            </td>
            {% endif %}
            <td>
              <a href="{{ url_for('panel', region=region, venta_id=v['id_venta'], _anchor='detalle-venta') }}">
                <button type="button" class="btn-sec">Ver detalle</button>
              </a>
            </td>
          </tr>
        {% endfor %}
      </table>

      {% if detalle_venta %}
        <h4 id="detalle-venta" style="margin-top:16px;">Detalle del Pedido / Venta #{{ venta_seleccionada }} ({{ region }}.detalle_venta)</h4>
        <table>
          <tr>
            {% for col in detalle_venta[0].keys() %}<th>{{ col }}</th>{% endfor %}
          </tr>
          {% for dv in detalle_venta %}
            <tr>{% for val in dv.values() %}<td>{{ val }}</td>{% endfor %}</tr>
          {% endfor %}
        </table>
      {% elif venta_seleccionada %}
        <p id="detalle-venta" style="font-size:13px;color:#475569;margin-top:10px;">Sin productos asociados a la venta #{{ venta_seleccionada }}.</p>
      {% endif %}
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin ventas registradas en {{ region }}.venta.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_facturas %}
  <div class="card">
    <h3>Consulta de Facturas ({{ region }}.factura)</h3>
    {% if facturas %}
      <table>
        <tr>
          {% for col in facturas[0].keys() %}<th>{{ col }}</th>{% endfor %}
          <th>Detalle</th>
        </tr>
        {% for f in facturas %}
          <tr>
            {% for val in f.values() %}<td>{{ val }}</td>{% endfor %}
            <td>
              <a href="{{ url_for('panel', region=region, factura_id=f['id_factura'], _anchor='detalle-factura') }}">
                <button type="button" class="btn-sec">Ver detalle</button>
              </a>
            </td>
          </tr>
        {% endfor %}
      </table>

      {% if detalle_factura %}
        <h4 id="detalle-factura" style="margin-top:16px;">Detalle de Factura #{{ factura_seleccionada }} ({{ region }}.detalle_venta)</h4>
        <table>
          <tr>
            {% for col in detalle_factura[0].keys() %}<th>{{ col }}</th>{% endfor %}
          </tr>
          {% for d in detalle_factura %}
            <tr>{% for val in d.values() %}<td>{{ val }}</td>{% endfor %}</tr>
          {% endfor %}
        </table>
      {% elif factura_seleccionada %}
        <p id="detalle-factura" style="font-size:13px;color:#475569;margin-top:10px;">Sin filas de detalle para la factura #{{ factura_seleccionada }}.</p>
      {% endif %}
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin facturas registradas en {{ region }}.factura.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_proveedores %}
  <div class="card">
    <h3>Consulta de Proveedores (central.proveedor)</h3>
    {% if proveedores %}
      <table>
        <tr>
          {% for col in proveedores[0].keys() %}<th>{{ col }}</th>{% endfor %}
        </tr>
        {% for pr in proveedores %}
          <tr>{% for val in pr.values() %}<td>{{ val }}</td>{% endfor %}</tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin proveedores registrados en central.proveedor.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_nomina %}
  <div class="card">
    <h3>Nómina / Talento Humano (central.empleado_nomina)</h3>
    {% if nomina %}
      <table>
        <tr>
          {% for col in nomina[0].keys() %}<th>{{ col }}</th>{% endfor %}
        </tr>
        {% for n in nomina %}
          <tr>{% for val in n.values() %}<td>{{ val }}</td>{% endfor %}</tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin registros en central.empleado_nomina.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if rol_cfg.puede_ver_auditoria %}
  <div class="card">
    <h3>Auditoría Central (central.auditoria)</h3>
    {% if auditorias %}
      <table>
        <tr>
          {% for col in auditorias[0].keys() %}<th>{{ col }}</th>{% endfor %}
        </tr>
        {% for a in auditorias %}
          <tr>{% for val in a.values() %}<td>{{ val }}</td>{% endfor %}</tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">Sin registros en central.auditoria.</p>
    {% endif %}
  </div>
  {% endif %}

  {% if puede_simular %}
  <div class="card">
    <h3>Monitor de Flujo, Réplicas y Particiones (Logs en vivo)</h3>
    {% if eventos_log %}
      <table>
        <tr>
          <th>Hora</th>
          <th>Categoría</th>
          <th>Flujo</th>
          <th>Modo</th>
          <th>Detalle</th>
        </tr>
        {% for ev in eventos_log %}
          <tr>
            <td>{{ ev.hora }}</td>
            <td>{{ ev.categoria }}</td>
            <td>{{ ev.origen }} &rarr; {{ ev.destino }}</td>
            <td><b>{{ ev.modo }}</b></td>
            <td>{{ ev.detalle }}</td>
          </tr>
        {% endfor %}
      </table>
    {% else %}
      <p style="font-size:13px;color:#475569;">Aún no se han registrado eventos de flujo o réplica en esta sesión del servidor.</p>
    {% endif %}
  </div>
  {% endif %}

  <script>
    (function () {
      const ids = {{ inventarios | map(attribute='id_inventario') | list | tojson }};
      document.querySelectorAll('form[action*="ajustar_stock"]').forEach(function (f) {
        const i = f.querySelector('input[name="id_inventario"]');
        if (!i) return;
        const vFn = function () {
          const v = i.value.trim();
          i.setCustomValidity(v !== '' && !ids.includes(Number(v)) ? 'El ID de inventario ' + v + ' no existe en {{ region }}.' : '');
        };
        i.addEventListener('input', vFn);
        i.addEventListener('change', vFn);
        vFn();
      });

      function configurarValidacionProducto(formId, nomId, catId, provId, precioId, pesoId) {
        const formProd = document.getElementById(formId);
        if (!formProd) return null;

        const nomProd = document.getElementById(nomId);
        const catProd = document.getElementById(catId);
        const provProd = document.getElementById(provId);
        const precioProd = document.getElementById(precioId);
        const pesoProd = document.getElementById(pesoId);

        function validarNombreProd() {
          const v = nomProd.value.trim();
          if (!v) {
            nomProd.setCustomValidity('El nombre del producto es obligatorio.');
          } else if (/^[0-9\s.\-/]+$/.test(v) || !/[A-Za-zÁÉÍÓÚáéíóúÑñÜü]/.test(v)) {
            nomProd.setCustomValidity('El nombre del producto no puede ser solo números; debe incluir letras (ej. iPhone 15).');
          } else if (v.length < 2 || v.length > 100) {
            nomProd.setCustomValidity('El nombre del producto debe tener entre 2 y 100 caracteres.');
          } else {
            nomProd.setCustomValidity('');
          }
        }

        function validarCatProd() {
          const num = Number(catProd.value);
          if (!catProd.value.trim() || !Number.isInteger(num) || num < 1) {
            catProd.setCustomValidity('El ID de categoría debe ser un número entero mayor o igual a 1.');
          } else {
            catProd.setCustomValidity('');
          }
        }

        function validarProvProd() {
          const v = provProd.value.trim();
          if (!v) {
            provProd.setCustomValidity('');
            return;
          }
          const num = Number(v);
          if (!Number.isInteger(num) || num < 1) {
            provProd.setCustomValidity('El ID de proveedor debe ser un número entero mayor o igual a 1.');
          } else {
            provProd.setCustomValidity('');
          }
        }

        function validarPrecioProd() {
          const num = Number(precioProd.value);
          if (!precioProd.value.trim() || Number.isNaN(num) || num <= 0) {
            precioProd.setCustomValidity('El precio debe ser un número mayor a 0.');
          } else {
            precioProd.setCustomValidity('');
          }
        }

        function validarPesoProd() {
          const v = pesoProd.value.trim();
          if (!v) {
            pesoProd.setCustomValidity('');
            return;
          }
          const num = Number(v);
          if (Number.isNaN(num) || num < 0) {
            pesoProd.setCustomValidity('El peso no puede ser negativo.');
          } else {
            pesoProd.setCustomValidity('');
          }
        }

        function validarTodoProducto() {
          validarNombreProd();
          validarCatProd();
          validarProvProd();
          validarPrecioProd();
          validarPesoProd();
        }

        [nomProd, catProd, provProd, precioProd, pesoProd].forEach(function (el) {
          if (!el) return;
          el.addEventListener('input', validarTodoProducto);
          el.addEventListener('change', validarTodoProducto);
        });

        formProd.addEventListener('submit', function (ev) {
          validarTodoProducto();
          if (!formProd.checkValidity()) {
            ev.preventDefault();
            formProd.reportValidity();
          }
        });

        return { nomProd, catProd, provProd, precioProd, pesoProd, validarTodoProducto };
      }

      configurarValidacionProducto(
        'form-crear-producto',
        'prod-nombre',
        'prod-cat',
        'prod-prov',
        'prod-precio',
        'prod-peso'
      );

      const editProdCtrl = configurarValidacionProducto(
        'form-editar-producto',
        'edit-prod-nombre',
        'edit-prod-cat',
        'edit-prod-prov',
        'edit-prod-precio',
        'edit-prod-peso'
      );
      const selEditProd = document.getElementById('edit-prod-select');
      const actEditProd = document.getElementById('edit-prod-activo');
      if (editProdCtrl && selEditProd) {
        const cargarProductoSeleccionado = function () {
          const opt = selEditProd.options[selEditProd.selectedIndex];
          if (!opt) return;
          editProdCtrl.nomProd.value = opt.dataset.nombre || '';
          editProdCtrl.catProd.value = opt.dataset.cat || '';
          editProdCtrl.provProd.value = opt.dataset.prov || '';
          editProdCtrl.precioProd.value = opt.dataset.precio || '';
          editProdCtrl.pesoProd.value = opt.dataset.peso || '';
          if (actEditProd) {
            actEditProd.value = opt.dataset.activo === 'false' ? 'false' : 'true';
          }
          editProdCtrl.validarTodoProducto();
        };
        selEditProd.addEventListener('change', cargarProductoSeleccionado);
        cargarProductoSeleccionado();
      }

      function configurarValidacionEmpleado(formId, nomId, docId, telId, cargoId, salId) {
        const formEmp = document.getElementById(formId);
        if (!formEmp) return null;

        const nomEmp = document.getElementById(nomId);
        const docEmp = document.getElementById(docId);
        const telEmp = document.getElementById(telId);
        const cargoEmp = document.getElementById(cargoId);
        const salEmp = document.getElementById(salId);

        function validarEmpNombre() {
          const v = nomEmp.value.trim();
          if (!v) {
            nomEmp.setCustomValidity('El nombre completo es obligatorio.');
          } else if (!/^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$/.test(v)) {
            nomEmp.setCustomValidity('El nombre completo solo puede contener letras y espacios.');
          } else if (v.length < 2 || v.length > 100) {
            nomEmp.setCustomValidity('El nombre completo debe tener entre 2 y 100 caracteres.');
          } else {
            nomEmp.setCustomValidity('');
          }
        }

        function validarEmpDoc() {
          const v = docEmp.value.trim();
          if (!v) {
            docEmp.setCustomValidity('El número de documento es obligatorio.');
          } else if (!/^[0-9]+$/.test(v)) {
            docEmp.setCustomValidity('El documento solo puede contener números.');
          } else if (v.length < 5 || v.length > 15) {
            docEmp.setCustomValidity('El documento debe tener entre 5 y 15 dígitos.');
          } else {
            docEmp.setCustomValidity('');
          }
        }

        function validarEmpTel() {
          const v = telEmp.value.trim();
          if (!v) {
            telEmp.setCustomValidity('El teléfono es obligatorio.');
          } else if (!/^[0-9]+$/.test(v)) {
            telEmp.setCustomValidity('El teléfono solo puede contener números.');
          } else if (v.length < 7 || v.length > 15) {
            telEmp.setCustomValidity('El teléfono debe tener entre 7 y 15 dígitos.');
          } else {
            telEmp.setCustomValidity('');
          }
        }

        function validarEmpCargo() {
          const v = cargoEmp.value.trim();
          if (!v) {
            cargoEmp.setCustomValidity('El cargo es obligatorio.');
          } else if (/[0-9]/.test(v)) {
            cargoEmp.setCustomValidity('El cargo no puede contener números.');
          } else if (!/^[A-Za-zÁÉÍÓÚáéíóúÑñÜü .\-/]+$/.test(v)) {
            cargoEmp.setCustomValidity('El cargo solo puede contener letras, espacios y caracteres básicos (sin números).');
          } else if (v.length < 2 || v.length > 80) {
            cargoEmp.setCustomValidity('El cargo debe tener entre 2 y 80 caracteres.');
          } else {
            cargoEmp.setCustomValidity('');
          }
        }

        function validarEmpSalario() {
          const num = Number(salEmp.value);
          if (!salEmp.value.trim() || Number.isNaN(num) || num <= 0) {
            salEmp.setCustomValidity('El salario debe ser un número mayor a 0.');
          } else {
            salEmp.setCustomValidity('');
          }
        }

        function validarTodoEmpleado() {
          validarEmpNombre();
          validarEmpDoc();
          validarEmpTel();
          validarEmpCargo();
          validarEmpSalario();
        }

        nomEmp.addEventListener('input', validarEmpNombre);
        nomEmp.addEventListener('change', validarEmpNombre);
        docEmp.addEventListener('input', validarEmpDoc);
        docEmp.addEventListener('change', validarEmpDoc);
        telEmp.addEventListener('input', validarEmpTel);
        telEmp.addEventListener('change', validarEmpTel);
        cargoEmp.addEventListener('input', validarEmpCargo);
        cargoEmp.addEventListener('change', validarEmpCargo);
        salEmp.addEventListener('input', validarEmpSalario);
        salEmp.addEventListener('change', validarEmpSalario);

        formEmp.addEventListener('submit', function (ev) {
          validarTodoEmpleado();
          if (!formEmp.checkValidity()) {
            ev.preventDefault();
            formEmp.reportValidity();
          }
        });

        return { nomEmp, docEmp, telEmp, cargoEmp, salEmp, validarTodoEmpleado };
      }

      configurarValidacionEmpleado(
        'form-crear-empleado',
        'emp-nombre',
        'emp-doc',
        'emp-tel',
        'emp-cargo',
        'emp-salario'
      );

      const editCtrl = configurarValidacionEmpleado(
        'form-editar-empleado',
        'edit-emp-nombre',
        'edit-emp-doc',
        'edit-emp-tel',
        'edit-emp-cargo',
        'edit-emp-salario'
      );
      const selEditEmp = document.getElementById('edit-emp-select');
      if (editCtrl && selEditEmp) {
        const cargarEmpleadoSeleccionado = function () {
          const opt = selEditEmp.options[selEditEmp.selectedIndex];
          if (!opt) return;
          editCtrl.nomEmp.value = opt.dataset.nombre || '';
          editCtrl.docEmp.value = opt.dataset.doc || '';
          editCtrl.telEmp.value = opt.dataset.tel || '';
          editCtrl.cargoEmp.value = opt.dataset.cargo || '';
          editCtrl.salEmp.value = opt.dataset.salario || '';
          editCtrl.validarTodoEmpleado();
        };
        selEditEmp.addEventListener('change', cargarEmpleadoSeleccionado);
        cargarEmpleadoSeleccionado();
      }

      const formComCli = document.getElementById('form-comercial-cliente');
      const selCliEdit = document.getElementById('select-cliente-editar');
      if (formComCli && selCliEdit) {
        const docInput = document.getElementById('com-num-doc');
        const nomInput = document.getElementById('com-nombre');
        const paisInput = document.getElementById('com-cod-pais');
        const telInput = document.getElementById('com-telefono');
        const dirInput = document.getElementById('com-direccion');

        function validarComDoc() {
          const v = docInput.value.trim();
          if (!v) {
            docInput.setCustomValidity('El número de documento es obligatorio.');
          } else if (!/^[0-9]+$/.test(v)) {
            docInput.setCustomValidity('El número de documento solo puede contener números (sin letras ni espacios).');
          } else if (v.length < 5 || v.length > 15) {
            docInput.setCustomValidity('El número de documento debe tener entre 5 y 15 dígitos.');
          } else {
            docInput.setCustomValidity('');
          }
        }

        function validarComNombre() {
          const v = nomInput.value.trim();
          if (!v) {
            nomInput.setCustomValidity('El nombre completo es obligatorio.');
          } else if (!/^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$/.test(v)) {
            nomInput.setCustomValidity('El nombre completo solo puede contener letras y espacios.');
          } else if (v.length < 2 || v.length > 100) {
            nomInput.setCustomValidity('El nombre completo debe tener entre 2 y 100 caracteres.');
          } else {
            nomInput.setCustomValidity('');
          }
        }

        function validarComPais() {
          const v = paisInput.value.trim();
          if (!v) {
            paisInput.setCustomValidity('El indicativo de país es obligatorio.');
          } else if (!/^\+?[0-9]{1,4}$/.test(v)) {
            paisInput.setCustomValidity('Usa un indicativo válido como +57 o 57 (1 a 4 dígitos).');
          } else {
            paisInput.setCustomValidity('');
          }
        }

        function validarComTel() {
          const v = telInput.value.trim();
          if (!v) {
            telInput.setCustomValidity('El teléfono es obligatorio.');
          } else if (!/^[0-9]+$/.test(v)) {
            telInput.setCustomValidity('El teléfono solo puede contener números (sin letras ni símbolos).');
          } else if (v.length < 7 || v.length > 15) {
            telInput.setCustomValidity('El teléfono debe tener entre 7 y 15 dígitos.');
          } else {
            telInput.setCustomValidity('');
          }
        }

        function validarComDir() {
          const v = dirInput.value.trim();
          if (!v) {
            dirInput.setCustomValidity('La dirección de envío es obligatoria.');
          } else if (v.length < 5 || v.length > 150) {
            dirInput.setCustomValidity('La dirección debe tener entre 5 y 150 caracteres.');
          } else {
            dirInput.setCustomValidity('');
          }
        }

        function validarTodoComercial() {
          validarComDoc();
          validarComNombre();
          validarComPais();
          validarComTel();
          validarComDir();
        }

        const cargarClienteSeleccionado = function () {
          const opt = selCliEdit.options[selCliEdit.selectedIndex];
          if (!opt) return;
          document.getElementById('com-tipo-doc').value = opt.dataset.tipo || 'CC';
          docInput.value = opt.dataset.doc || '';
          nomInput.value = opt.dataset.nombre || '';
          paisInput.value = opt.dataset.pais || '+57';
          telInput.value = opt.dataset.tel || '';
          dirInput.value = opt.dataset.dir || '';
          validarTodoComercial();
        };

        selCliEdit.addEventListener('change', cargarClienteSeleccionado);
        docInput.addEventListener('input', validarComDoc);
        docInput.addEventListener('change', validarComDoc);
        nomInput.addEventListener('input', validarComNombre);
        nomInput.addEventListener('change', validarComNombre);
        paisInput.addEventListener('input', validarComPais);
        paisInput.addEventListener('change', validarComPais);
        telInput.addEventListener('input', validarComTel);
        telInput.addEventListener('change', validarComTel);
        dirInput.addEventListener('input', validarComDir);
        dirInput.addEventListener('change', validarComDir);

        formComCli.addEventListener('submit', function (ev) {
          validarTodoComercial();
          if (!formComCli.checkValidity()) {
            ev.preventDefault();
            formComCli.reportValidity();
          }
        });

        cargarClienteSeleccionado();
      }

      const formCli = document.getElementById('form-cliente-datos');
      if (formCli) {
        const docInput = formCli.querySelector('input[name="numero_documento"]');
        const nomInput = formCli.querySelector('input[name="nombre"]');
        const telInput = formCli.querySelector('input[name="numero_telefono"]');

        function validarDoc() {
          const v = docInput.value.trim();
          if (!v) {
            docInput.setCustomValidity('');
          } else if (!/^[0-9]+$/.test(v)) {
            docInput.setCustomValidity('El número de documento solo puede contener números.');
          } else if (v.length < 5 || v.length > 15) {
            docInput.setCustomValidity('El número de documento debe tener entre 5 y 15 dígitos.');
          } else {
            docInput.setCustomValidity('');
          }
        }

        function validarNombre() {
          const v = nomInput.value.trim();
          if (!v) {
            nomInput.setCustomValidity('');
          } else if (!/^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$/.test(v)) {
            nomInput.setCustomValidity('El nombre completo solo puede contener letras y espacios.');
          } else if (v.length < 2) {
            nomInput.setCustomValidity('Ingresa un nombre válido (mínimo 2 letras).');
          } else {
            nomInput.setCustomValidity('');
          }
        }

        function validarTel() {
          const v = telInput.value.trim();
          if (!v) {
            telInput.setCustomValidity('');
          } else if (!/^[0-9]+$/.test(v)) {
            telInput.setCustomValidity('El teléfono solo puede contener números (sin letras ni símbolos).');
          } else if (v.length < 7 || v.length > 15) {
            telInput.setCustomValidity('El teléfono debe tener entre 7 y 15 dígitos.');
          } else {
            telInput.setCustomValidity('');
          }
        }

        docInput.addEventListener('input', validarDoc);
        docInput.addEventListener('change', validarDoc);
        nomInput.addEventListener('input', validarNombre);
        nomInput.addEventListener('change', validarNombre);
        telInput.addEventListener('input', validarTel);
        telInput.addEventListener('change', validarTel);

        formCli.addEventListener('submit', function (ev) {
          validarDoc();
          validarNombre();
          validarTel();
          if (!formCli.checkValidity()) {
            ev.preventDefault();
            formCli.reportValidity();
          }
        });
      }
    })();
  </script>
</body>
</html>
"""


def get_conn(rol_key):
    cfg = ROLES_CONFIG[rol_key]
    conn_kwargs = {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": cfg["db_user"],
        "password": cfg["db_pass"],
        "cursor_factory": RealDictCursor,
    }
    if DB_HOST not in ("localhost", "127.0.0.1"):
        conn_kwargs["sslmode"] = "require"
    return psycopg2.connect(**conn_kwargs)


def es_consulta_segura(sql_raw):
    limpio = sql_raw.strip()
    if not limpio:
        return False, "Escribe una consulta SQL antes de ejecutar."
    if limpio.endswith(";"):
        limpio = limpio[:-1].strip()
    if ";" in limpio:
        return False, "Solo se permite una consulta de lectura a la vez (no se permiten múltiples sentencias)."

    sin_strings = re.sub(r"'(?:''|[^'])*'", " ", limpio)
    palabras = re.findall(r"[a-zA-Z_]+", sin_strings.lower())
    if not palabras:
        return False, "Consulta SQL no válida."

    inicio_permitido = {"select", "with", "explain", "show", "table", "values"}
    if palabras[0] not in inicio_permitido:
        return False, "Solo se permiten consultas de lectura (SELECT, WITH, EXPLAIN, SHOW). No se permite modificar ni eliminar datos."

    prohibidas = {
        "insert", "update", "delete", "drop", "alter", "truncate",
        "create", "replace", "grant", "revoke", "vacuum", "copy",
        "call", "do", "set", "lock", "comment", "refresh", "merge",
        "into", "attach", "detach", "reindex", "cluster"
    }
    if any(p in prohibidas for p in palabras):
        return False, "Consulta bloqueada: contiene palabras clave de escritura, borrado o modificación."

    return True, None


def obtener_empleados_nomina_enriquecidos(cur, conn, region_activa):
    cur.execute("SELECT id_empleado, fecha_contratacion, salario, cargo FROM central.empleado_nomina ORDER BY id_empleado")
    filas_nomina = cur.fetchall()
    if not filas_nomina:
        return []

    mapa_identificacion = {}
    esquemas_a_consultar = [region_activa] + [r for r in ("bogota", "manizales", "cartagena") if r != region_activa]
    for reg in esquemas_a_consultar:
        if not ESTADO_NODOS.get(reg, True):
            continue
        try:
            cur.execute(
                f"SELECT id_empleado, nombre, numero_documento, numero_telefono FROM {reg}.empleado_identificacion"
            )
            for emp in cur.fetchall():
                if emp["id_empleado"] not in mapa_identificacion:
                    mapa_identificacion[emp["id_empleado"]] = emp
        except Exception:
            conn.rollback()

    resultado = []
    for row in filas_nomina:
        emp_id = row["id_empleado"]
        ident = mapa_identificacion.get(emp_id, {})
        item = {
            "id_empleado": emp_id,
            "nombre": ident.get("nombre") or "—",
            "fecha_contratacion": row["fecha_contratacion"],
            "salario": row["salario"],
            "cargo": row["cargo"],
            "numero_documento": ident.get("numero_documento") or "",
            "numero_telefono": ident.get("numero_telefono") or "",
        }
        resultado.append(item)
    return resultado


def validar_datos_empleado(nombre, numero_documento, numero_telefono, cargo, salario_raw):
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}", nombre):
        return None, "El nombre completo solo debe contener letras y espacios (2 a 100 caracteres)."
    if not re.fullmatch(r"[0-9]{5,15}", numero_documento):
        return None, "El documento solo debe contener números (5 a 15 dígitos)."
    if not re.fullmatch(r"[0-9]{7,15}", numero_telefono):
        return None, "El teléfono solo debe contener números (7 a 15 dígitos)."
    if re.search(r"[0-9]", cargo) or not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü .\-/]{2,80}", cargo):
        return None, "El cargo no puede contener números y debe tener entre 2 y 80 caracteres válidos."
    try:
        salario = float(salario_raw)
        if salario <= 0:
            raise ValueError()
    except Exception:
        return None, "El salario debe ser un número válido mayor a 0."
    return salario, None


def validar_datos_producto(nombre, id_categoria_raw, id_proveedor_raw, precio_raw, peso_raw):
    if len(nombre) < 2 or len(nombre) > 100:
        return None, "El nombre del producto debe tener entre 2 y 100 caracteres."
    if re.fullmatch(r"[0-9\s.\-/]+", nombre) or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]", nombre):
        return None, "El nombre del producto no puede ser solo números; debe contener letras (ej. iPhone 15)."
    try:
        id_categoria = int(id_categoria_raw)
        if id_categoria < 1:
            raise ValueError()
    except Exception:
        return None, "El ID de categoría debe ser un número entero mayor o igual a 1."

    id_proveedor = None
    if id_proveedor_raw:
        try:
            id_proveedor = int(id_proveedor_raw)
            if id_proveedor < 1:
                raise ValueError()
        except Exception:
            return None, "El ID de proveedor debe ser un número entero mayor o igual a 1."

    try:
        precio = float(precio_raw)
        if precio <= 0:
            raise ValueError()
    except Exception:
        return None, "El precio debe ser un número válido mayor a 0."

    peso = None
    if peso_raw:
        try:
            peso = float(peso_raw)
            if peso < 0:
                raise ValueError()
        except Exception:
            return None, "El peso debe ser un número válido mayor o igual a 0."

    return {
        "nombre": nombre,
        "id_categoria": id_categoria,
        "id_proveedor": id_proveedor,
        "precio": precio,
        "peso": peso,
    }, None


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        rol = request.form.get("rol")
        clave = request.form.get("clave", "")
        if rol in ROLES_CONFIG and clave == ROLES_CONFIG[rol]["db_pass"]:
            session["rol"] = rol
            session["carrito_reservas"] = []
            session.pop("cliente_id", None)
            session.pop("sql_resultado", None)
            session.pop("sql_query", None)
            registrar_evento("SESION", "cliente_web", rol, f"Ingreso exitoso al rol {rol}", "NORMAL")
            return redirect(url_for("panel"))
        error = "Rol o contraseña incorrectos."
    return render_template_string(HTML_LOGIN, roles=ROLES_CONFIG, error=error)


@app.route("/logout")
def logout():
    rol = session.get("rol", "desconocido")
    registrar_evento("SESION", rol, "login", "Cierre de sesión", "NORMAL")
    session.clear()
    return redirect(url_for("login"))


@app.route("/nodo/<nodo>/<accion>", methods=["POST"])
def cambiar_nodo(nodo, accion):
    region = request.form.get("region", "bogota")
    if session.get("rol") != "director_operaciones":
        return redirect(url_for("panel", region=region, err="Solo el Director de Operaciones puede simular caídas."))
    if nodo in ESTADO_NODOS and accion in ("caer", "levantar"):
        ESTADO_NODOS[nodo] = (accion == "levantar")
        estado_txt = "ACTIVO" if ESTADO_NODOS[nodo] else "CAÍDO (simulado)"
        modo_txt = "NORMAL" if ESTADO_NODOS[nodo] else "PARTICION"
        registrar_evento(
            "TOPOLOGIA",
            "director_operaciones",
            nodo,
            f"Cambio de estado de nodo '{nodo}' a {estado_txt}",
            modo_txt,
        )
    estado = "ACTIVO" if ESTADO_NODOS[nodo] else "CAÍDO (simulado)"
    return redirect(url_for("panel", region=region, msg=f"Nodo {nodo}: {estado}"))


@app.route("/ejecutar_sql", methods=["POST"])
def ejecutar_sql():
    rol = session.get("rol")
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    if rol != "director_operaciones":
        return redirect(url_for("panel", region=region, err="Solo el Director de Operaciones puede usar la consola SQL."))

    sql_query = (request.form.get("sql_query") or "").strip()
    session["sql_query"] = sql_query

    valida, motivo = es_consulta_segura(sql_query)
    if not valida:
        session.pop("sql_resultado", None)
        registrar_evento("SQL_BLOQUEADO", rol, "PostgreSQL", f"Bloqueado SQL no permitido: {sql_query[:80]}", "NORMAL")
        return redirect(url_for("panel", region=region, err=motivo))

    try:
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql_query)
            filas = [dict(r) for r in cur.fetchall()] if cur.description is not None else []
            conn.rollback()
            session["sql_resultado"] = filas
            registrar_evento("SQL_CONSULTA", rol, "PostgreSQL", f"Consulta de lectura ejecutada ({len(filas)} fila(s))", "NORMAL")
            return redirect(url_for("panel", region=region, msg=f"Consulta ejecutada correctamente. Filas retornadas: {len(filas)}."))
    except Exception as e:
        session.pop("sql_resultado", None)
        return redirect(url_for("panel", region=region, err=f"Error al ejecutar consulta SQL: {e}"))


@app.route("/panel")
def panel():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG:
        return redirect(url_for("login"))
    cfg = ROLES_CONFIG[rol]
    region = request.args.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    factura_seleccionada = request.args.get("factura_id")
    venta_seleccionada = request.args.get("venta_id")
    msg = request.args.get("msg")
    err = request.args.get("err")
    errores_bd = []
    inventarios = []
    catalogo = []
    productos_central_editables = []
    clientes = []
    clientes_menu = []
    proveedores = []
    ventas = []
    detalle_venta = []
    facturas = []
    detalle_factura = []
    nomina = []
    empleados_editables = []
    auditorias = []
    productos = []
    bodegas = []
    cliente_actual = None
    carrito_items = []
    tienda_catalogo = []
    sql_query = session.get("sql_query", "")
    sql_resultado = session.get("sql_resultado") if rol == "director_operaciones" else None

    try:
        with get_conn(rol) as conn, conn.cursor() as cur:
            if cfg.get("es_cliente"):
                try:
                    cur.execute(
                        f"""
                        SELECT p.id_producto, p.nombre, p.precio,
                               i.id_inventario, i.id_bodega,
                               COALESCE(i.cantidad, 0) - COALESCE((
                                   SELECT SUM(r.cantidad)
                                   FROM {region}.reserva_stock r
                                   WHERE r.id_inventario = i.id_inventario
                                     AND r.estado = 'ACTIVA'
                                     AND (r.expira_en IS NULL OR r.expira_en > NOW())
                               ), 0) AS disponible
                        FROM {region}.producto p
                        LEFT JOIN {region}.inventario i ON i.id_producto = p.id_producto
                        ORDER BY p.id_producto
                        """
                    )
                    tienda_catalogo = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[Catálogo cliente {region}]: {e}")

                carrito_ids = [x for x in session.get("carrito_reservas", []) if isinstance(x, int)]
                if carrito_ids:
                    try:
                        cur.execute(
                            f"""
                            SELECT r.id_reserva, r.cantidad, r.expira_en,
                                   i.id_bodega, p.nombre, p.precio,
                                   (r.cantidad * p.precio) AS subtotal
                            FROM {region}.reserva_stock r
                            JOIN {region}.inventario i ON i.id_inventario = r.id_inventario
                            JOIN {region}.producto p ON p.id_producto = i.id_producto
                            WHERE r.id_reserva = ANY(%s)
                              AND r.estado = 'ACTIVA'
                            ORDER BY r.id_reserva
                            """,
                            (carrito_ids,),
                        )
                        carrito_items = cur.fetchall()
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[Carrito cliente {region}]: {e}")

                if session.get("cliente_id"):
                    try:
                        cur.execute(f"SELECT * FROM {region}.cliente WHERE id_cliente = %s", (session["cliente_id"],))
                        cliente_actual = cur.fetchone()
                    except Exception:
                        conn.rollback()

            if not cfg.get("solo_comercial"):
                try:
                    cur.execute(f"SELECT * FROM {region}.inventario ORDER BY id_inventario")
                    inventarios = cur.fetchall()
                except Exception:
                    conn.rollback()

                if rol != "analista_nomina" and not cfg.get("es_cliente"):
                    try:
                        cur.execute(f"SELECT * FROM {region}.producto ORDER BY id_producto DESC")
                        catalogo = cur.fetchall()
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[{region}.producto]: {e}")

            if (cfg.get("puede_editar_producto_central") or cfg.get("puede_eliminar_producto_central")) and ESTADO_NODOS["central"]:
                try:
                    cur.execute("SELECT * FROM central.producto ORDER BY id_producto")
                    productos_central_editables = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[central.producto]: {e}")

            if cfg["puede_ver_clientes"]:
                try:
                    cur.execute(
                        f"""
                        SELECT id_cliente, tipo_documento, numero_documento, nombre,
                               codigo_pais, numero_telefono, direccion, region
                        FROM {region}.cliente
                        ORDER BY id_cliente DESC
                        """
                    )
                    clientes = cur.fetchall()
                    clientes_menu = clientes
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[{region}.cliente]: {e}")

            if cfg.get("puede_ver_proveedores"):
                if not ESTADO_NODOS["central"]:
                    errores_bd.append("[central] nodo caído (simulado): proveedores no disponibles")
                else:
                    try:
                        cur.execute("SELECT * FROM central.proveedor ORDER BY id_proveedor DESC")
                        proveedores = cur.fetchall()
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[central.proveedor]: {e}")

            if cfg.get("puede_ver_ventas"):
                try:
                    cur.execute(f"SELECT * FROM {region}.venta ORDER BY id_venta DESC")
                    ventas = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[{region}.venta]: {e}")

                if venta_seleccionada and venta_seleccionada.isdigit():
                    try:
                        cur.execute(
                            f"""
                            SELECT dv.id_venta, dv.id_producto, p.nombre AS producto,
                                   p.id_proveedor, dv.id_bodega, dv.cantidad,
                                   dv.precio_unitario, (dv.cantidad * dv.precio_unitario) AS subtotal
                            FROM {region}.detalle_venta dv
                            LEFT JOIN {region}.producto p ON p.id_producto = dv.id_producto
                            WHERE dv.id_venta = %s
                            """,
                            (int(venta_seleccionada),),
                        )
                        detalle_venta = cur.fetchall()
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[Detalle venta #{venta_seleccionada}]: {e}")

            if cfg["puede_ver_facturas"]:
                try:
                    cur.execute(f"SELECT * FROM {region}.factura ORDER BY id_factura DESC")
                    facturas = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[{region}.factura]: {e}")

                if factura_seleccionada and factura_seleccionada.isdigit():
                    try:
                        cur.execute(
                            f"""
                            SELECT dv.id_venta, dv.id_producto, p.nombre AS producto,
                                   p.id_proveedor, dv.id_bodega, dv.cantidad,
                                   dv.precio_unitario, v.id_cliente, v.estado
                            FROM {region}.detalle_venta dv
                            JOIN {region}.venta v ON v.id_venta = dv.id_venta
                            LEFT JOIN {region}.producto p ON p.id_producto = dv.id_producto
                            WHERE v.id_factura = %s
                            """,
                            (int(factura_seleccionada),),
                        )
                        detalle_factura = cur.fetchall()
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[Detalle factura #{factura_seleccionada}]: {e}")

            if cfg["puede_vender"]:
                for sql, destino in [
                    (f"SELECT id_producto, nombre, precio FROM {region}.producto ORDER BY id_producto", "productos"),
                    (f"SELECT id_bodega, nombre FROM {region}.bodega ORDER BY id_bodega", "bodegas"),
                ]:
                    try:
                        cur.execute(sql)
                        rows = cur.fetchall()
                        if destino == "productos":
                            productos = rows
                        elif destino == "bodegas":
                            bodegas = rows
                    except Exception as e:
                        conn.rollback()
                        errores_bd.append(f"[Catálogo {destino}]: {e}")

            if not ESTADO_NODOS["central"] and (cfg["puede_ver_nomina"] or cfg["puede_ver_auditoria"]):
                errores_bd.append("[central] nodo caído (simulado): nómina y auditoría no disponibles")

            if cfg["puede_ver_nomina"] and ESTADO_NODOS["central"]:
                try:
                    if rol == "analista_nomina":
                        enriquecidos = obtener_empleados_nomina_enriquecidos(cur, conn, region)
                        empleados_editables = enriquecidos
                        nomina = [
                            {
                                "id_empleado": r["id_empleado"],
                                "nombre": r["nombre"],
                                "fecha_contratacion": r["fecha_contratacion"],
                                "salario": r["salario"],
                                "cargo": r["cargo"],
                            }
                            for r in enriquecidos
                        ]
                    else:
                        cur.execute("SELECT * FROM central.empleado_nomina ORDER BY id_empleado")
                        nomina = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[central.empleado_nomina]: {e}")

            if cfg["puede_ver_auditoria"] and ESTADO_NODOS["central"]:
                try:
                    cur.execute("SELECT * FROM central.auditoria ORDER BY 1 DESC")
                    auditorias = cur.fetchall()
                except Exception as e:
                    conn.rollback()
                    errores_bd.append(f"[central.auditoria]: {e}")
    except Exception as e:
        errores_bd.append(f"[Conexión PostgreSQL]: {e}")

    err_final = "\n".join([x for x in [err] + errores_bd if x])

    return render_template_string(
        HTML_PANEL,
        rol_cfg=cfg,
        region=region,
        estados_venta=ESTADOS_VENTA,
        inventarios=inventarios,
        catalogo=catalogo,
        productos_central_editables=productos_central_editables,
        clientes=clientes,
        clientes_menu=clientes_menu,
        proveedores=proveedores,
        ventas=ventas,
        detalle_venta=detalle_venta,
        venta_seleccionada=venta_seleccionada,
        facturas=facturas,
        detalle_factura=detalle_factura,
        factura_seleccionada=factura_seleccionada,
        nomina=nomina,
        empleados_editables=empleados_editables,
        auditorias=auditorias,
        productos=productos,
        bodegas=bodegas,
        cliente_actual=cliente_actual,
        carrito_items=carrito_items,
        tienda_catalogo=tienda_catalogo,
        sql_query=sql_query,
        sql_resultado=sql_resultado,
        msg=msg,
        err=err_final if err_final else None,
        estado_nodos=ESTADO_NODOS,
        puede_simular=(rol == "director_operaciones"),
        eventos_log=LOG_EVENTOS,
    )


@app.route("/comercial/cliente/actualizar", methods=["POST"])
def comercial_actualizar_cliente():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("puede_actualizar_clientes"):
        return redirect(url_for("panel", err="Permiso denegado para actualizar clientes."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    id_cliente_raw = request.form.get("id_cliente", "").strip()
    tipo_doc = request.form.get("tipo_documento", "CC").strip().upper()
    num_doc = request.form.get("numero_documento", "").strip()
    nombre = request.form.get("nombre", "").strip()
    cod_pais = request.form.get("codigo_pais", "+57").strip() or "+57"
    telefono = request.form.get("numero_telefono", "").strip()
    direccion = request.form.get("direccion", "").strip()

    tipos_validos = {"CC", "CE", "TI", "NIT", "PASAPORTE", "DNI", "RUT"}
    if not id_cliente_raw.isdigit():
        return redirect(url_for("panel", region=region, err="Selecciona un cliente válido para actualizar."))
    if tipo_doc not in tipos_validos:
        return redirect(url_for("panel", region=region, err="Tipo de documento no válido."))
    if not re.fullmatch(r"[0-9]{5,15}", num_doc):
        return redirect(url_for("panel", region=region, err="El número de documento solo debe contener números (5 a 15 dígitos)."))
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}", nombre):
        return redirect(url_for("panel", region=region, err="El nombre completo solo debe contener letras y espacios (2 a 100 caracteres)."))
    if not re.fullmatch(r"\+?[0-9]{1,4}", cod_pais):
        return redirect(url_for("panel", region=region, err="El indicativo de país debe tener formato como +57 o 57 (1 a 4 dígitos)."))
    if not re.fullmatch(r"[0-9]{7,15}", telefono):
        return redirect(url_for("panel", region=region, err="El teléfono solo debe contener números (7 a 15 dígitos)."))
    if len(direccion) < 5 or len(direccion) > 150:
        return redirect(url_for("panel", region=region, err="La dirección de envío debe tener entre 5 y 150 caracteres."))

    try:
        id_cli = int(id_cliente_raw)
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {region}.cliente
                SET tipo_documento = %s, numero_documento = %s, nombre = %s,
                    codigo_pais = %s, numero_telefono = %s, direccion = %s
                WHERE id_cliente = %s
                """,
                (tipo_doc, num_doc, nombre, cod_pais, telefono, direccion, id_cli),
            )
            conn.commit()
        registrar_evento("CLIENTE", rol, f"{region}.cliente", f"Actualizado cliente #{id_cli} ('{nombre}')", modo)
        return redirect(url_for("panel", region=region, msg=f"Cliente #{id_cli} ('{nombre}') actualizado en {region}.cliente."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al actualizar cliente: {e}"))


@app.route("/comercial/venta/estado", methods=["POST"])
def comercial_actualizar_estado_venta():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("puede_gestionar_estado_venta"):
        return redirect(url_for("panel", err="Permiso denegado para actualizar ventas."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    id_venta_raw = request.form.get("id_venta", "").strip()
    nuevo_estado = request.form.get("estado", "").strip().upper()
    if not id_venta_raw.isdigit() or not nuevo_estado:
        return redirect(url_for("panel", region=region, err="Datos de venta o estado inválidos."))

    try:
        id_venta = int(id_venta_raw)
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {region}.venta SET estado = %s WHERE id_venta = %s",
                (nuevo_estado, id_venta),
            )
            conn.commit()
        registrar_evento("VENTA", rol, f"{region}.venta", f"Venta #{id_venta} -> estado {nuevo_estado}", modo)
        return redirect(url_for("panel", region=region, msg=f"Pedido/Venta #{id_venta} actualizado a '{nuevo_estado}' en {region}.venta."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al actualizar estado de venta: {e}"))


@app.route("/cliente/datos", methods=["POST"])
def cliente_guardar_datos():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("es_cliente"):
        return redirect(url_for("panel", err="Permiso denegado."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    region_upper = region.upper()
    tipo_doc = request.form.get("tipo_documento", "CC").strip()
    num_doc = request.form.get("numero_documento", "").strip()
    nombre = request.form.get("nombre", "").strip()
    cod_pais = request.form.get("codigo_pais", "+57").strip() or "+57"
    telefono = request.form.get("numero_telefono", "").strip()
    direccion = request.form.get("direccion", "").strip() or None

    if not re.fullmatch(r"[0-9]{5,15}", num_doc):
        return redirect(url_for("panel", region=region, err="El número de documento solo debe contener números (5 a 15 dígitos)."))
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,100}", nombre):
        return redirect(url_for("panel", region=region, err="El nombre completo solo debe contener letras y espacios."))
    if not re.fullmatch(r"[0-9]{7,15}", telefono):
        return redirect(url_for("panel", region=region, err="El teléfono solo debe contener números (7 a 15 dígitos)."))

    try:
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id_cliente FROM {region}.cliente WHERE numero_documento = %s", (num_doc,))
            row = cur.fetchone()
            if row:
                id_cliente = row["id_cliente"]
                cur.execute(
                    f"""
                    UPDATE {region}.cliente
                    SET tipo_documento = %s, nombre = %s, codigo_pais = %s, numero_telefono = %s, direccion = %s
                    WHERE id_cliente = %s
                    """,
                    (tipo_doc, nombre, cod_pais, telefono, direccion, id_cliente),
                )
            else:
                cur.execute(f"SELECT COALESCE(MAX(id_cliente), 0) + 1 AS next_id FROM {region}.cliente")
                id_cliente = cur.fetchone()["next_id"]
                cur.execute(
                    f"""
                    INSERT INTO {region}.cliente
                        (id_cliente, tipo_documento, numero_documento, nombre, codigo_pais, numero_telefono, direccion, region)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (id_cliente, tipo_doc, num_doc, nombre, cod_pais, telefono, direccion, region_upper),
                )
            conn.commit()
        session["cliente_id"] = id_cliente
        registrar_evento("CLIENTE", "Cliente", f"{region}.cliente", f"Datos guardados para cliente #{id_cliente} ('{nombre}')", modo)
        return redirect(url_for("panel", region=region, msg=f"Datos guardados en {region}.cliente (ID #{id_cliente})."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al guardar datos de cliente: {e}"))


@app.route("/cliente/carrito/agregar", methods=["POST"])
def cliente_agregar_carrito():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("es_cliente"):
        return redirect(url_for("panel", err="Permiso denegado."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    try:
        id_inventario = int(request.form["id_inventario"])
        cantidad = int(request.form["cantidad"])
        if cantidad < 1:
            raise ValueError("La cantidad debe ser al menos 1.")
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        expira_en = datetime.now() + timedelta(hours=2)
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT i.cantidad - COALESCE((
                    SELECT SUM(r.cantidad)
                    FROM {region}.reserva_stock r
                    WHERE r.id_inventario = i.id_inventario
                      AND r.estado = 'ACTIVA'
                      AND (r.expira_en IS NULL OR r.expira_en > NOW())
                ), 0) AS disponible
                FROM {region}.inventario i
                WHERE i.id_inventario = %s
                """,
                (id_inventario,),
            )
            inv = cur.fetchone()
            if not inv or inv["disponible"] < cantidad:
                raise ValueError("Stock insuficiente para reservar esa cantidad.")
            cur.execute(f"SELECT COALESCE(MAX(id_reserva), 0) + 1 AS next_id FROM {region}.reserva_stock")
            id_reserva = cur.fetchone()["next_id"]
            cur.execute(
                f"""
                INSERT INTO {region}.reserva_stock (id_reserva, id_inventario, cantidad, estado, expira_en)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (id_reserva, id_inventario, cantidad, "ACTIVA", expira_en),
            )
            conn.commit()
        carrito = session.get("carrito_reservas", [])
        carrito.append(id_reserva)
        session["carrito_reservas"] = carrito
        registrar_evento("CARRITO", "Cliente", f"{region}.reserva_stock", f"Reserva #{id_reserva} (inv #{id_inventario}, cant {cantidad})", modo)
        return redirect(url_for("panel", region=region, msg=f"Producto reservado en carrito (Reserva #{id_reserva} en {region}.reserva_stock)."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al agregar al carrito: {e}"))


@app.route("/cliente/carrito/quitar/<int:id_reserva>", methods=["POST"])
def cliente_quitar_carrito(id_reserva):
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("es_cliente"):
        return redirect(url_for("panel", err="Permiso denegado."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    try:
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {region}.reserva_stock WHERE id_reserva = %s", (id_reserva,))
            conn.commit()
        session["carrito_reservas"] = [r for r in session.get("carrito_reservas", []) if r != id_reserva]
        registrar_evento("CARRITO", "Cliente", f"{region}.reserva_stock", f"Eliminada reserva #{id_reserva}", modo)
        return redirect(url_for("panel", region=region, msg=f"Reserva #{id_reserva} eliminada del carrito."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al quitar del carrito: {e}"))


@app.route("/cliente/comprar", methods=["POST"])
def cliente_confirmar_compra():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("es_cliente"):
        return redirect(url_for("panel", err="Permiso denegado."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    region_upper = region.upper()
    id_cliente = session.get("cliente_id")
    carrito_ids = [x for x in session.get("carrito_reservas", []) if isinstance(x, int)]
    metodo_pago = request.form.get("metodo_pago", "EFECTIVO").strip()

    if not id_cliente:
        return redirect(url_for("panel", region=region, err="Primero ingresa y guarda tus datos personales antes de confirmar la compra."))
    if not carrito_ids:
        return redirect(url_for("panel", region=region, err="Tu carrito está vacío."))

    try:
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.id_reserva, r.id_inventario, r.cantidad, i.id_bodega, i.id_producto, p.precio
                FROM {region}.reserva_stock r
                JOIN {region}.inventario i ON i.id_inventario = r.id_inventario
                JOIN {region}.producto p ON p.id_producto = i.id_producto
                WHERE r.id_reserva = ANY(%s) AND r.estado = 'ACTIVA'
                """,
                (carrito_ids,),
            )
            items = cur.fetchall()
            if not items:
                raise ValueError("No hay reservas activas en el carrito.")

            total_pagar = round(sum(float(it["precio"]) * int(it["cantidad"]) for it in items), 2)

            cur.execute(f"SELECT COALESCE(MAX(id_factura), 0) + 1 AS next_id FROM {region}.factura")
            id_factura = cur.fetchone()["next_id"]
            cur.execute(
                f"""
                INSERT INTO {region}.factura (id_factura, fecha, total_pagar, metodo_pago)
                VALUES (%s, %s, %s, %s)
                """,
                (id_factura, datetime.now(), total_pagar, metodo_pago),
            )

            cur.execute(f"SELECT COALESCE(MAX(id_venta), 0) + 1 AS next_id FROM {region}.venta")
            id_venta = cur.fetchone()["next_id"]
            cur.execute(
                f"""
                INSERT INTO {region}.venta (id_venta, id_factura, id_cliente, estado, region)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (id_venta, id_factura, id_cliente, "COMPLETADA", region_upper),
            )

            for it in items:
                cur.execute(
                    f"""
                    INSERT INTO {region}.detalle_venta (id_venta, id_producto, id_bodega, cantidad, precio_unitario)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_venta, it["id_producto"], it["id_bodega"], int(it["cantidad"]), float(it["precio"])),
                )

            cur.execute(f"DELETE FROM {region}.reserva_stock WHERE id_reserva = ANY(%s)", (carrito_ids,))
            conn.commit()

        session["carrito_reservas"] = []
        registrar_evento(
            "COMPRA_REGIONAL",
            "Cliente",
            f"{region}.venta / {region}.factura",
            f"Compra confirmada en {region}: Venta #{id_venta}, Factura #{id_factura}, Total ${total_pagar}",
            modo,
        )
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Compra confirmada. Venta #{id_venta} y Factura #{id_factura} registradas en {region} (Total: ${total_pagar}).",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al confirmar compra: {e}"))


@app.route("/vender", methods=["POST"])
def vender():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol]["puede_vender"]:
        return redirect(url_for("panel", err="Permiso denegado para registrar ventas."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    region_upper = region.upper()

    id_cliente_existente = request.form.get("id_cliente_existente", "").strip()
    cliente_nombre = request.form.get("cliente_nombre", "").strip()
    cliente_tipo_doc = request.form.get("cliente_tipo_doc", "CC").strip()
    cliente_documento = request.form.get("cliente_documento", "").strip()
    codigo_pais = request.form.get("codigo_pais", "+57").strip() or "+57"
    cliente_telefono = request.form.get("cliente_telefono", "").strip()
    cliente_direccion = request.form.get("cliente_direccion", "").strip() or None
    id_producto = int(request.form["id_producto"])
    id_bodega = int(request.form["id_bodega"])
    cantidad = int(request.form["cantidad"])
    metodo_pago = request.form.get("metodo_pago", "EFECTIVO").strip()

    try:
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT precio FROM {region}.producto WHERE id_producto = %s", (id_producto,))
            prod_row = cur.fetchone()
            if not prod_row:
                raise ValueError(f"El producto {id_producto} no existe en {region}.producto.")
            precio_unitario = float(prod_row["precio"])
            total_pagar = round(cantidad * precio_unitario, 2)

            if id_cliente_existente.isdigit():
                id_cliente = int(id_cliente_existente)
                cur.execute(f"SELECT nombre FROM {region}.cliente WHERE id_cliente = %s", (id_cliente,))
                cli_row = cur.fetchone()
                if not cli_row:
                    raise ValueError(f"El cliente {id_cliente} no existe en {region}.cliente.")
                nombre_log = cli_row["nombre"]
            else:
                if not cliente_nombre or not cliente_documento or not cliente_telefono:
                    raise ValueError("Si no eliges un cliente existente, debes completar nombre, identificación y teléfono.")
                cur.execute(f"SELECT COALESCE(MAX(id_cliente), 0) + 1 AS next_id FROM {region}.cliente")
                id_cliente = cur.fetchone()["next_id"]
                cur.execute(
                    f"""
                    INSERT INTO {region}.cliente
                        (id_cliente, tipo_documento, numero_documento, nombre, codigo_pais, numero_telefono, direccion, region)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (id_cliente, cliente_tipo_doc, cliente_documento, cliente_nombre, codigo_pais, cliente_telefono, cliente_direccion, region_upper),
                )
                nombre_log = cliente_nombre

            cur.execute(f"SELECT COALESCE(MAX(id_factura), 0) + 1 AS next_id FROM {region}.factura")
            id_factura = cur.fetchone()["next_id"]
            cur.execute(
                f"""
                INSERT INTO {region}.factura (id_factura, fecha, total_pagar, metodo_pago)
                VALUES (%s, %s, %s, %s)
                """,
                (id_factura, datetime.now(), total_pagar, metodo_pago),
            )

            cur.execute(f"SELECT COALESCE(MAX(id_venta), 0) + 1 AS next_id FROM {region}.venta")
            id_venta = cur.fetchone()["next_id"]
            cur.execute(
                f"""
                INSERT INTO {region}.venta (id_venta, id_factura, id_cliente, estado, region)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (id_venta, id_factura, id_cliente, "COMPLETADA", region_upper),
            )

            cur.execute(
                f"""
                INSERT INTO {region}.detalle_venta (id_venta, id_producto, id_bodega, cantidad, precio_unitario)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (id_venta, id_producto, id_bodega, cantidad, precio_unitario),
            )

            conn.commit()
        registrar_evento("VENTA", rol, f"{region}.venta", f"Venta #{id_venta} (Factura #{id_factura}, Total ${total_pagar})", modo)
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Venta #{id_venta} registrada en {region} (Cliente: {nombre_log}, Factura #{id_factura}, Total: ${total_pagar}).",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al registrar venta: {e}"))


@app.route("/ajustar_stock", methods=["POST"])
def ajustar_stock():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol]["puede_ajustar_inventario"]:
        return redirect(url_for("panel", err="Permiso denegado para ajustar inventario."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    try:
        modo = "CONTINGENCIA" if not ESTADO_NODOS[region] else "NORMAL"
        id_inv = int(request.form["id_inventario"])
        nueva_cant = int(request.form["nueva_cantidad"])
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {region}.inventario SET cantidad = %s WHERE id_inventario = %s",
                (nueva_cant, id_inv),
            )
            conn.commit()
        registrar_evento("INVENTARIO", rol, f"{region}.inventario", f"Inv #{id_inv} -> nueva cantidad {nueva_cant}", modo)
        return redirect(url_for("panel", region=region, msg=f"Inventario actualizado en {region}.inventario."))
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"PostgreSQL bloqueó el ajuste de stock: {e}"))


@app.route("/crear_producto_central", methods=["POST"])
def crear_producto_central():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol]["puede_crear_producto_central"]:
        return redirect(url_for("panel", err="Permiso denegado para crear productos en central."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    datos, err_val = validar_datos_producto(
        request.form.get("nombre", "").strip(),
        request.form.get("id_categoria", "").strip(),
        request.form.get("id_proveedor", "").strip(),
        request.form.get("precio", "").strip(),
        request.form.get("peso", "").strip(),
    )
    if err_val:
        return redirect(url_for("panel", region=region, err=err_val))

    try:
        exigir_nodo("central")
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id_producto), 0) + 1 AS next_id FROM central.producto")
            id_producto = cur.fetchone()["next_id"]
            cur.execute(
                """
                INSERT INTO central.producto (id_producto, nombre, id_categoria, id_proveedor, precio, peso, activo)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                """,
                (
                    id_producto,
                    datos["nombre"],
                    datos["id_categoria"],
                    datos["id_proveedor"],
                    datos["precio"],
                    datos["peso"],
                ),
            )
            conn.commit()
        registrar_evento("REPLICA_INSERT", rol, "central.producto -> regiones", f"Creado producto #{id_producto} ('{datos['nombre']}')", "NORMAL")
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Producto #{id_producto} ('{datos['nombre']}') creado en central.producto y replicado por triggers a las regiones.",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al crear producto central: {e}"))


@app.route("/editar_producto_central", methods=["POST"])
def editar_producto_central():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("puede_editar_producto_central"):
        return redirect(url_for("panel", err="Permiso denegado para editar productos en central."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    id_producto_raw = request.form.get("id_producto", "").strip()
    if not id_producto_raw.isdigit():
        return redirect(url_for("panel", region=region, err="Selecciona un producto válido para editar."))

    datos, err_val = validar_datos_producto(
        request.form.get("nombre", "").strip(),
        request.form.get("id_categoria", "").strip(),
        request.form.get("id_proveedor", "").strip(),
        request.form.get("precio", "").strip(),
        request.form.get("peso", "").strip(),
    )
    if err_val:
        return redirect(url_for("panel", region=region, err=err_val))

    activo_raw = request.form.get("activo", "true").strip().lower()
    if activo_raw not in ("true", "false"):
        return redirect(url_for("panel", region=region, err="Estado del producto no válido."))
    activo = activo_raw == "true"

    try:
        exigir_nodo("central")
        id_producto = int(id_producto_raw)
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE central.producto
                SET nombre = %s, id_categoria = %s, id_proveedor = %s, precio = %s, peso = %s, activo = %s
                WHERE id_producto = %s
                """,
                (
                    datos["nombre"],
                    datos["id_categoria"],
                    datos["id_proveedor"],
                    datos["precio"],
                    datos["peso"],
                    activo,
                    id_producto,
                ),
            )
            conn.commit()
        registrar_evento("REPLICA_UPDATE", rol, "central.producto -> regiones", f"Editado producto #{id_producto} ('{datos['nombre']}')", "NORMAL")
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Producto #{id_producto} ('{datos['nombre']}') actualizado en central.producto.",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al editar producto central: {e}"))


@app.route("/eliminar_producto_central", methods=["POST"])
def eliminar_producto_central():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("puede_eliminar_producto_central"):
        return redirect(url_for("panel", err="Permiso denegado para eliminar productos en central."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    id_producto_raw = request.form.get("id_producto", "").strip()
    if not id_producto_raw.isdigit():
        return redirect(url_for("panel", region=region, err="Selecciona un producto válido para eliminar."))

    try:
        exigir_nodo("central")
        id_producto = int(id_producto_raw)
        with get_conn(rol) as conn, conn.cursor() as cur:
            for reg in ("bogota", "manizales", "cartagena"):
                cur.execute(
                    f"""
                    DELETE FROM {reg}.reserva_stock
                    WHERE id_inventario IN (
                        SELECT id_inventario FROM {reg}.inventario WHERE id_producto = %s
                    )
                    """,
                    (id_producto,),
                )
                cur.execute(f"DELETE FROM {reg}.inventario WHERE id_producto = %s", (id_producto,))
                cur.execute(f"DELETE FROM {reg}.detalle_venta WHERE id_producto = %s", (id_producto,))

            cur.execute("DELETE FROM central.producto WHERE id_producto = %s RETURNING nombre", (id_producto,))
            eliminado = cur.fetchone()
            if not eliminado:
                raise ValueError(f"El producto #{id_producto} no existe en central.producto.")
            conn.commit()
        registrar_evento("REPLICA_DELETE", rol, "central.producto -> regiones", f"Eliminado producto #{id_producto} ('{eliminado['nombre']}') y sus referencias regionales", "NORMAL")
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Producto #{id_producto} ('{eliminado['nombre']}') eliminado de central.producto y de las regiones.",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al eliminar producto central: {e}"))


@app.route("/crear_empleado", methods=["POST"])
def crear_empleado():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol]["puede_crear_empleado"]:
        return redirect(url_for("panel", err="Permiso denegado para registrar empleados."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"
    region_upper = region.upper()

    nombre = request.form.get("nombre", "").strip()
    numero_documento = request.form.get("numero_documento", "").strip()
    numero_telefono = request.form.get("numero_telefono", "").strip()
    cargo = request.form.get("cargo", "").strip()
    salario_raw = request.form.get("salario", "").strip()

    salario, error_val = validar_datos_empleado(nombre, numero_documento, numero_telefono, cargo, salario_raw)
    if error_val:
        return redirect(url_for("panel", region=region, err=error_val))

    try:
        exigir_nodo("central")
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX(id_empleado), 0) + 1 AS next_id FROM {region}.empleado_identificacion")
            next_reg = cur.fetchone()["next_id"]
            cur.execute("SELECT COALESCE(MAX(id_empleado), 0) + 1 AS next_id FROM central.empleado_nomina")
            next_cen = cur.fetchone()["next_id"]
            id_empleado = max(next_reg, next_cen)

            cur.execute(
                f"""
                INSERT INTO {region}.empleado_identificacion
                    (id_empleado, tipo_documento, numero_documento, nombre, codigo_pais, numero_telefono, direccion, region)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (id_empleado, "CC", numero_documento, nombre, "+57", numero_telefono, None, region_upper),
            )
            cur.execute(
                """
                INSERT INTO central.empleado_nomina (id_empleado, fecha_contratacion, salario, cargo)
                VALUES (%s, %s, %s, %s)
                """,
                (id_empleado, datetime.now().date(), salario, cargo),
            )
            conn.commit()
        registrar_evento("EMPLEADO_INSERT", rol, f"{region}.empleado_identificacion + central.empleado_nomina", f"Alta empleado #{id_empleado} ('{nombre}')", "NORMAL")
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Empleado #{id_empleado} ('{nombre}') guardado en {region}.empleado_identificacion y central.empleado_nomina.",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al registrar empleado: {e}"))


@app.route("/editar_empleado", methods=["POST"])
def editar_empleado():
    rol = session.get("rol")
    if rol not in ROLES_CONFIG or not ROLES_CONFIG[rol].get("puede_editar_empleado"):
        return redirect(url_for("panel", err="Permiso denegado para editar empleados."))
    region = request.form.get("region", "bogota")
    if region not in ("bogota", "manizales", "cartagena"):
        region = "bogota"

    id_empleado_raw = request.form.get("id_empleado", "").strip()
    nombre = request.form.get("nombre", "").strip()
    numero_documento = request.form.get("numero_documento", "").strip()
    numero_telefono = request.form.get("numero_telefono", "").strip()
    cargo = request.form.get("cargo", "").strip()
    salario_raw = request.form.get("salario", "").strip()

    if not id_empleado_raw.isdigit():
        return redirect(url_for("panel", region=region, err="Selecciona un empleado válido para editar."))

    salario, error_val = validar_datos_empleado(nombre, numero_documento, numero_telefono, cargo, salario_raw)
    if error_val:
        return redirect(url_for("panel", region=region, err=error_val))

    try:
        exigir_nodo("central")
        id_empleado = int(id_empleado_raw)
        with get_conn(rol) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE central.empleado_nomina
                SET salario = %s, cargo = %s
                WHERE id_empleado = %s
                """,
                (salario, cargo, id_empleado),
            )
            cur.execute(
                f"""
                UPDATE {region}.empleado_identificacion
                SET nombre = %s, numero_documento = %s, numero_telefono = %s
                WHERE id_empleado = %s
                """,
                (nombre, numero_documento, numero_telefono, id_empleado),
            )
            conn.commit()
        registrar_evento("EMPLEADO_UPDATE", rol, f"{region}.empleado_identificacion + central.empleado_nomina", f"Actualizado empleado #{id_empleado} ('{nombre}')", "NORMAL")
        return redirect(
            url_for(
                "panel",
                region=region,
                msg=f"Empleado #{id_empleado} ('{nombre}') actualizado en {region}.empleado_identificacion y central.empleado_nomina.",
            )
        )
    except Exception as e:
        return redirect(url_for("panel", region=region, err=f"Error al editar empleado: {e}"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
