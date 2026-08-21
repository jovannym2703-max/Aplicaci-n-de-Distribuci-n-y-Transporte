"""
Módulo: Gestión de Pedidos
Crea, confirma y controla el ciclo de vida de los pedidos, validando
disponibilidad contra el módulo de Inventario.
"""

from typing import Dict, List

from modelos import Cliente, EstadoPedido, ItemPedido, Pedido, Producto
from inventario import GestionInventario


class GestionPedidos:
    def __init__(self, inventario: GestionInventario):
        self._inventario = inventario
        self._pedidos: Dict[str, Pedido] = {}
        self._contador = 0

    def crear_pedido(self, cliente: Cliente, items: List[ItemPedido]) -> Pedido:
        self._contador += 1
        pedido = Pedido(id=f"PED-{self._contador:04d}", cliente=cliente, items=items)
        self._pedidos[pedido.id] = pedido
        return pedido

    def confirmar_pedido(self, pedido_id: str) -> Pedido:
        pedido = self._obtener(pedido_id)
        for item in pedido.items:
            if not self._inventario.hay_disponibilidad(item.producto.codigo, item.cantidad):
                raise ValueError(f"Sin stock suficiente para {item.producto.nombre} en el pedido {pedido_id}")
        for item in pedido.items:
            self._inventario.salida_stock(item.producto.codigo, item.cantidad, referencia=pedido_id)
        pedido.estado = EstadoPedido.CONFIRMADO
        return pedido

    def cancelar_pedido(self, pedido_id: str, devolver_stock: bool = True) -> Pedido:
        pedido = self._obtener(pedido_id)
        if pedido.estado == EstadoPedido.CONFIRMADO and devolver_stock:
            for item in pedido.items:
                self._inventario.entrada_stock(item.producto.codigo, item.cantidad, referencia=f"cancelación {pedido_id}")
        pedido.estado = EstadoPedido.CANCELADO
        return pedido

    def marcar_asignado(self, pedido_id: str) -> None:
        self._obtener(pedido_id).estado = EstadoPedido.ASIGNADO

    def marcar_entregado(self, pedido_id: str) -> None:
        self._obtener(pedido_id).estado = EstadoPedido.ENTREGADO

    def listar_por_estado(self, estado: EstadoPedido) -> List[Pedido]:
        return [p for p in self._pedidos.values() if p.estado == estado]

    def _obtener(self, pedido_id: str) -> Pedido:
        if pedido_id not in self._pedidos:
            raise KeyError(f"Pedido no encontrado: {pedido_id}")
        return self._pedidos[pedido_id]
