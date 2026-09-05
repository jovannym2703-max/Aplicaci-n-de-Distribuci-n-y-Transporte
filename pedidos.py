"""
Módulo: Gestión de Pedidos
===========================
Administra el ciclo de vida completo de un pedido: creación, confirmación
(con descuento de inventario), backorder ante faltantes de stock,
asignación a una ruta de despacho, entrega y cancelación (con reintegro
de stock si aplica).

Este módulo era importado por app.py y reportes.py en el proyecto
original pero no existía en el repositorio — se reconstruye aquí
siguiendo exactamente la interfaz que ya usaban ambos archivos, y se
amplía con manejo de backorders, prioridad de pedidos y trazabilidad de
tiempos de ciclo (fecha de creación vs. fecha de entrega real), que son
la base de indicadores logísticos como OTIF y Fill Rate.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from inventario import GestionInventario
from modelos import Cliente, EstadoPedido, ItemPedido, Pedido, Prioridad


class GestionPedidos:
    def __init__(self, inventario: GestionInventario):
        self._inventario = inventario
        self._pedidos: Dict[str, Pedido] = {}
        self._contador = 0

    # ------------------------------------------------------------------
    def crear_pedido(self, cliente: Cliente, items: List[ItemPedido],
                      prioridad: Prioridad = Prioridad.NORMAL, notas: str = "") -> Pedido:
        if not items:
            raise ValueError("El pedido debe contener al menos un producto.")
        self._contador += 1
        pid = f"PED-{self._contador:04d}"

        # el lead time comprometido se estima con el mayor lead time de reposición
        # entre los productos del pedido (regla conservadora simple)
        lead_time = max((i.producto.lead_time_dias for i in items), default=3)
        holgura = {Prioridad.URGENTE: 0, Prioridad.ALTA: 1, Prioridad.NORMAL: 2, Prioridad.BAJA: 4}.get(prioridad, 2)

        pedido = Pedido(
            id=pid,
            cliente=cliente,
            items=items,
            prioridad=prioridad,
            fecha_entrega_estimada=datetime.now() + timedelta(days=lead_time + holgura),
            notas=notas,
        )
        self._pedidos[pid] = pedido
        return pedido

    def confirmar_pedido(self, pedido_id: str) -> Pedido:
        """Confirma el pedido y descuenta inventario. Si algún ítem no
        tiene stock suficiente, el pedido pasa a BACKORDER (no se descuenta
        nada) y se lanza un ValueError informativo para la interfaz."""
        pedido = self._obtener(pedido_id)
        if pedido.estado not in (EstadoPedido.CREADO, EstadoPedido.BACKORDER):
            raise ValueError(f"El pedido {pedido_id} no se puede confirmar desde el estado {pedido.estado.value}.")

        faltantes = [
            i for i in pedido.items
            if not self._inventario.hay_disponibilidad(i.producto.codigo, i.cantidad)
        ]
        if faltantes:
            pedido.estado = EstadoPedido.BACKORDER
            nombres = ", ".join(f"{i.producto.nombre} (faltan {i.cantidad - self._inventario.consultar_stock(i.producto.codigo)})" for i in faltantes)
            raise ValueError(f"Stock insuficiente para: {nombres}. Pedido marcado como BACKORDER.")

        for item in pedido.items:
            self._inventario.salida_stock(item.producto.codigo, item.cantidad, referencia=pedido.id)
        pedido.estado = EstadoPedido.CONFIRMADO
        return pedido

    def marcar_asignado(self, pedido_id: str) -> Pedido:
        pedido = self._obtener(pedido_id)
        if pedido.estado != EstadoPedido.CONFIRMADO:
            raise ValueError(f"Solo un pedido CONFIRMADO puede asignarse a una ruta (estado actual: {pedido.estado.value}).")
        pedido.estado = EstadoPedido.ASIGNADO
        return pedido

    def marcar_entregado(self, pedido_id: str) -> Pedido:
        pedido = self._obtener(pedido_id)
        pedido.estado = EstadoPedido.ENTREGADO
        pedido.fecha_entrega_real = datetime.now()
        return pedido

    def cancelar_pedido(self, pedido_id: str) -> Pedido:
        pedido = self._obtener(pedido_id)
        if pedido.estado in (EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO):
            raise ValueError(f"Un pedido {pedido.estado.value} no se puede cancelar.")
        # si ya se había descontado inventario (CONFIRMADO o ASIGNADO), se reintegra
        if pedido.estado in (EstadoPedido.CONFIRMADO, EstadoPedido.ASIGNADO):
            for item in pedido.items:
                self._inventario.entrada_stock(item.producto.codigo, item.cantidad, referencia=f"Reintegro por cancelación {pedido.id}")
        pedido.estado = EstadoPedido.CANCELADO
        return pedido

    # ------------------------------------------------------------------
    def listar_por_estado(self, estado: EstadoPedido) -> List[Pedido]:
        return [p for p in self._pedidos.values() if p.estado == estado]

    def obtener_pedido(self, pedido_id: str) -> Pedido:
        return self._obtener(pedido_id)

    def listar_pedidos(self) -> List[Pedido]:
        return list(self._pedidos.values())

    # ------------------------------------------------------------------
    # Indicadores de servicio al cliente basados en pedidos
    # ------------------------------------------------------------------
    def tiempo_ciclo_promedio(self) -> float:
        """Promedio de días entre creación y entrega real, sobre pedidos entregados."""
        entregados = self.listar_por_estado(EstadoPedido.ENTREGADO)
        tiempos = [p.tiempo_ciclo_dias for p in entregados if p.tiempo_ciclo_dias is not None]
        return round(sum(tiempos) / len(tiempos), 2) if tiempos else 0.0

    def tasa_entregas_a_tiempo(self) -> float:
        """% de pedidos entregados dentro de la fecha estimada (componente 'On Time' de OTIF)."""
        entregados = self.listar_por_estado(EstadoPedido.ENTREGADO)
        evaluables = [p for p in entregados if p.entregado_a_tiempo is not None]
        if not evaluables:
            return 0.0
        a_tiempo = sum(1 for p in evaluables if p.entregado_a_tiempo)
        return round((a_tiempo / len(evaluables)) * 100, 1)

    def fill_rate(self) -> float:
        """% de pedidos que se pudieron confirmar sin caer en backorder,
        sobre el total de pedidos que ya pasaron por el intento de confirmación."""
        estados_relevantes = (EstadoPedido.CONFIRMADO, EstadoPedido.ASIGNADO, EstadoPedido.ENTREGADO, EstadoPedido.BACKORDER)
        relevantes = [p for p in self._pedidos.values() if p.estado in estados_relevantes]
        if not relevantes:
            return 0.0
        sin_backorder = [p for p in relevantes if p.estado != EstadoPedido.BACKORDER]
        return round((len(sin_backorder) / len(relevantes)) * 100, 1)

    # ------------------------------------------------------------------
    def _obtener(self, pedido_id: str) -> Pedido:
        if pedido_id not in self._pedidos:
            raise KeyError(f"Pedido no encontrado: {pedido_id}")
        return self._pedidos[pedido_id]
