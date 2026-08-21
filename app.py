"""
Aplicación web — Sistema de Gestión de Distribución y Transporte
==================================================================
Interfaz Streamlit que conecta los módulos de lógica de negocio:
  inventario.py | pedidos.py | transporte.py | rastreo.py | reportes.py

Ejecutar localmente:   streamlit run app.py
"""

import streamlit as st
import pandas as pd

from modelos import Cliente, EstadoEnvio, EstadoPedido, ItemPedido, Producto, Vehiculo
from inventario import GestionInventario
from pedidos import GestionPedidos
from transporte import GestionTransporte
from rastreo import GestionRastreo
import reportes

st.set_page_config(page_title="Gestión de Distribución y Transporte", layout="wide")

# ---------------------------------------------------------------------------
# Estado persistente entre interacciones (Streamlit vuelve a correr el script
# en cada clic, por eso los objetos de gestión viven en st.session_state).
# ---------------------------------------------------------------------------
if "inventario" not in st.session_state:
    st.session_state.inventario = GestionInventario()
    st.session_state.pedidos_mgr = GestionPedidos(st.session_state.inventario)
    st.session_state.transporte = GestionTransporte()
    st.session_state.rastreo = GestionRastreo()
    st.session_state.rutas = []      # historial de rutas calculadas (para KPI)
    st.session_state.envios = []     # historial de envíos creados

inventario: GestionInventario = st.session_state.inventario
pedidos_mgr: GestionPedidos = st.session_state.pedidos_mgr
transporte: GestionTransporte = st.session_state.transporte
rastreo: GestionRastreo = st.session_state.rastreo


# ---------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------
st.sidebar.title("📦 Distribución y Transporte")
pagina = st.sidebar.radio(
    "Módulo",
    ["Dashboard", "Inventario", "Pedidos", "Transporte y Rutas", "Rastreo", "Reportes"],
)

# ===========================================================================
# DASHBOARD
# ===========================================================================
if pagina == "Dashboard":
    st.title("Dashboard general")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Productos en inventario", len(inventario._productos))
    col2.metric("Pedidos registrados", len(pedidos_mgr._pedidos))
    col3.metric("Vehículos en flota", len(transporte._flota))
    col4.metric("Envíos generados", len(st.session_state.envios))

    st.divider()
    st.subheader("Pedidos por estado")
    if pedidos_mgr._pedidos:
        conteo = pd.Series(
            [p.estado.value for p in pedidos_mgr._pedidos.values()]
        ).value_counts()
        st.bar_chart(conteo)
    else:
        st.info("Aún no hay pedidos registrados. Ve al módulo **Pedidos** para crear el primero.")

# ===========================================================================
# INVENTARIO
# ===========================================================================
elif pagina == "Inventario":
    st.title("Gestión de Inventario")

    with st.expander("➕ Registrar nuevo producto"):
        with st.form("form_producto"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código (SKU)")
            nombre = c2.text_input("Nombre del producto")
            c3, c4, c5 = st.columns(3)
            categoria = c3.text_input("Categoría")
            peso = c4.number_input("Peso unitario (kg)", min_value=0.0, step=0.1)
            volumen = c5.number_input("Volumen unitario (m³)", min_value=0.0, step=0.01)
            c6, c7 = st.columns(2)
            stock_min = c6.number_input("Stock mínimo", min_value=0, step=1)
            stock_inicial = c7.number_input("Stock inicial", min_value=0, step=1)
            if st.form_submit_button("Registrar producto"):
                if codigo and nombre:
                    producto = Producto(codigo, nombre, categoria, peso, volumen, stock_min)
                    inventario.registrar_producto(producto, stock_inicial=int(stock_inicial))
                    st.success(f"Producto {codigo} registrado.")
                else:
                    st.error("Código y nombre son obligatorios.")

    st.subheader("Stock actual")
    if inventario._productos:
        filas = [{
            "Código": c, "Nombre": p.nombre, "Categoría": p.categoria,
            "Stock": inventario.consultar_stock(c), "Stock mínimo": p.stock_minimo,
            "Bajo mínimo": "⚠️" if inventario.consultar_stock(c) < p.stock_minimo else "",
        } for c, p in inventario._productos.items()]
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        st.subheader("Movimiento de stock")
        codigo_sel = st.selectbox("Producto", list(inventario._productos.keys()))
        c1, c2, c3 = st.columns(3)
        cantidad = c1.number_input("Cantidad", min_value=1, step=1, key="mov_cant")
        tipo_mov = c2.selectbox("Tipo", ["ENTRADA", "SALIDA"])
        if c3.button("Aplicar movimiento", use_container_width=True):
            try:
                if tipo_mov == "ENTRADA":
                    inventario.entrada_stock(codigo_sel, int(cantidad), referencia="ajuste manual")
                else:
                    inventario.salida_stock(codigo_sel, int(cantidad), referencia="ajuste manual")
                st.success("Movimiento aplicado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    else:
        st.info("No hay productos registrados todavía.")

# ===========================================================================
# PEDIDOS
# ===========================================================================
elif pagina == "Pedidos":
    st.title("Gestión de Pedidos")

    if not inventario._productos:
        st.warning("Registra al menos un producto en el módulo **Inventario** antes de crear pedidos.")
    else:
        with st.expander("➕ Crear nuevo pedido"):
            with st.form("form_pedido"):
                c1, c2 = st.columns(2)
                nombre_cliente = c1.text_input("Nombre del cliente")
                direccion = c2.text_input("Dirección")
                c3, c4 = st.columns(2)
                coord_x = c3.number_input("Coordenada X (ubicación simplificada)", step=1.0)
                coord_y = c4.number_input("Coordenada Y (ubicación simplificada)", step=1.0)

                st.caption("Productos del pedido")
                items_sel = st.multiselect("Selecciona productos", list(inventario._productos.keys()))
                cantidades = {}
                for codigo in items_sel:
                    cantidades[codigo] = st.number_input(
                        f"Cantidad de {inventario._productos[codigo].nombre}",
                        min_value=1, step=1, key=f"cant_{codigo}"
                    )

                if st.form_submit_button("Crear pedido"):
                    if nombre_cliente and items_sel:
                        cliente = Cliente(nombre_cliente, direccion, (coord_x, coord_y))
                        items = [ItemPedido(inventario._productos[c], int(cantidades[c])) for c in items_sel]
                        pedido = pedidos_mgr.crear_pedido(cliente, items)
                        st.success(f"Pedido {pedido.id} creado.")
                    else:
                        st.error("Nombre del cliente y al menos un producto son obligatorios.")

        st.subheader("Pedidos registrados")
        if pedidos_mgr._pedidos:
            filas = [{
                "ID": p.id, "Cliente": p.cliente.nombre, "Estado": p.estado.value,
                "Peso (kg)": round(p.peso_total, 2), "Volumen (m³)": round(p.volumen_total, 2),
            } for p in pedidos_mgr._pedidos.values()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            st.subheader("Confirmar o cancelar pedido")
            pedido_id = st.selectbox("Pedido", list(pedidos_mgr._pedidos.keys()))
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar pedido", use_container_width=True):
                try:
                    pedidos_mgr.confirmar_pedido(pedido_id)
                    st.success("Pedido confirmado y stock descontado.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if c2.button("❌ Cancelar pedido", use_container_width=True):
                pedidos_mgr.cancelar_pedido(pedido_id)
                st.success("Pedido cancelado.")
                st.rerun()
        else:
            st.info("No hay pedidos todavía.")

# ===========================================================================
# TRANSPORTE Y RUTAS
# ===========================================================================
elif pagina == "Transporte y Rutas":
    st.title("Gestión de Transporte")

    with st.expander("➕ Registrar vehículo"):
        with st.form("form_vehiculo"):
            c1, c2 = st.columns(2)
            placa = c1.text_input("Placa")
            tipo = c2.text_input("Tipo (camión, furgón, moto...)")
            c3, c4 = st.columns(2)
            cap_peso = c3.number_input("Capacidad de peso (kg)", min_value=0.0, step=10.0)
            cap_vol = c4.number_input("Capacidad de volumen (m³)", min_value=0.0, step=0.5)
            c5, c6 = st.columns(2)
            costo_km = c5.number_input("Costo por km ($)", min_value=0.0, step=100.0)
            costo_fijo = c6.number_input("Costo fijo de despacho ($)", min_value=0.0, step=1000.0)
            if st.form_submit_button("Registrar vehículo"):
                if placa:
                    transporte.registrar_vehiculo(
                        Vehiculo(placa, tipo, cap_peso, cap_vol, costo_km, costo_fijo)
                    )
                    st.success(f"Vehículo {placa} registrado.")
                else:
                    st.error("La placa es obligatoria.")

    st.subheader("Flota")
    if transporte._flota:
        filas = [{
            "Placa": v.placa, "Tipo": v.tipo, "Cap. peso (kg)": v.capacidad_peso_kg,
            "Cap. volumen (m³)": v.capacidad_volumen_m3, "Disponible": "Sí" if v.disponible else "No",
        } for v in transporte._flota.values()]
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        st.subheader("Calcular ruta")
        pendientes = pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)
        disponibles = transporte.vehiculos_disponibles()

        if not pendientes:
            st.info("No hay pedidos CONFIRMADOS pendientes de asignar. Confirma pedidos en el módulo **Pedidos**.")
        elif not disponibles:
            st.info("No hay vehículos disponibles. Registra uno arriba.")
        else:
            placa_sel = st.selectbox("Vehículo", [v.placa for v in disponibles])
            c1, c2 = st.columns(2)
            origen_x = c1.number_input("Origen X (centro de distribución)", value=0.0, step=1.0)
            origen_y = c2.number_input("Origen Y (centro de distribución)", value=0.0, step=1.0)

            st.caption(f"Pedidos confirmados pendientes: {[p.id for p in pendientes]}")

            if st.button("🚚 Asignar y calcular ruta óptima"):
                vehiculo = transporte._flota[placa_sel]
                asignados, no_asignados = transporte.asignar_pedidos_a_vehiculo(pendientes, vehiculo)
                if not asignados:
                    st.error("Ningún pedido cabe en la capacidad de este vehículo.")
                else:
                    ruta = transporte.calcular_ruta_optima((origen_x, origen_y), vehiculo, asignados)
                    for p in asignados:
                        pedidos_mgr.marcar_asignado(p.id)
                    envio = rastreo.crear_envio(ruta)
                    st.session_state.rutas.append(ruta)
                    st.session_state.envios.append(envio.id)

                    st.success(f"Ruta {ruta.id} calculada — Envío {envio.id} creado.")
                    st.write(f"**Secuencia de entrega:** {' → '.join(p.cliente.nombre for p in ruta.secuencia_pedidos)}")
                    st.write(f"**Distancia total:** {ruta.distancia_km} km")
                    st.write(f"**Costo estimado:** ${ruta.costo_estimado:,.0f}")
                    if no_asignados:
                        st.warning(f"No cupieron en este viaje: {[p.id for p in no_asignados]}")

                    # Visualización simple del recorrido
                    puntos = [(origen_x, origen_y)] + [p.cliente.coordenadas for p in ruta.secuencia_pedidos] + [(origen_x, origen_y)]
                    df_mapa = pd.DataFrame(puntos, columns=["x", "y"])
                    st.line_chart(df_mapa.set_index("x"))
    else:
        st.info("No hay vehículos registrados todavía.")

# ===========================================================================
# RASTREO
# ===========================================================================
elif pagina == "Rastreo":
    st.title("Rastreo y Trazabilidad de Envíos")

    if not st.session_state.envios:
        st.info("Aún no se ha generado ningún envío. Calcula una ruta en **Transporte y Rutas** primero.")
    else:
        envio_id = st.selectbox("Envío", st.session_state.envios)
        estado_actual = rastreo.consultar_estado(envio_id)
        st.metric("Estado actual", estado_actual.value)

        nuevo_estado = st.selectbox("Actualizar estado a:", [e.value for e in EstadoEnvio])
        nota = st.text_input("Nota (opcional)")
        if st.button("Actualizar estado"):
            rastreo.actualizar_estado(envio_id, EstadoEnvio(nuevo_estado), nota)
            if EstadoEnvio(nuevo_estado) == EstadoEnvio.ENTREGADO:
                for p in rastreo._envios[envio_id].ruta.secuencia_pedidos:
                    pedidos_mgr.marcar_entregado(p.id)
            st.success("Estado actualizado.")
            st.rerun()

        st.subheader("Historial")
        hist = rastreo.historial(envio_id)
        df_hist = pd.DataFrame(
            [{"Fecha": f, "Estado": e.value, "Nota": n} for f, e, n in hist]
        )
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ===========================================================================
# REPORTES
# ===========================================================================
elif pagina == "Reportes":
    st.title("Reportes e Indicadores (KPI)")

    col1, col2, col3 = st.columns(3)
    col1.metric("Nivel de servicio", f"{reportes.nivel_servicio(pedidos_mgr)}%")
    col2.metric("Costo promedio por envío", f"${reportes.costo_promedio_envio(st.session_state.rutas):,.0f}")
    col3.metric("Utilización de flota", f"{reportes.utilizacion_flota(transporte)}%")

    st.divider()
    st.subheader("Productos bajo stock mínimo")
    bajo_min = inventario.productos_bajo_minimo()
    if bajo_min:
        st.dataframe(
            pd.DataFrame([{"Código": p.codigo, "Nombre": p.nombre} for p in bajo_min]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("Ningún producto está bajo el stock mínimo.")

    st.subheader("Rutas calculadas")
    if st.session_state.rutas:
        st.dataframe(
            pd.DataFrame([{
                "Ruta": r.id, "Vehículo": r.vehiculo.placa,
                "Distancia (km)": r.distancia_km, "Costo ($)": r.costo_estimado,
            } for r in st.session_state.rutas]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no se han calculado rutas.")
