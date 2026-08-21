"""
Módulo: Gestión de Inventario
Controla existencias de productos, movimientos (kardex) y alertas de stock mínimo.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from modelos import Producto


@dataclass
class MovimientoInventario:
    producto_codigo: str
    tipo: str          # "ENTRADA" | "SALIDA"
    cantidad: int
    fecha: datetime = field(default_factory=datetime.now)
    referencia: str = ""


class GestionInventario:
    def __init__(self):
        self._productos: Dict[str, Producto] = {}
        self._stock: Dict[str, int] = {}
        self._kardex: List[MovimientoInventario] = []

    def registrar_producto(self, producto: Producto, stock_inicial: int = 0) -> None:
        self._productos[producto.codigo] = producto
        self._stock[producto.codigo] = stock_inicial
        if stock_inicial:
            self._kardex.append(MovimientoInventario(producto.codigo, "ENTRADA", stock_inicial, referencia="stock inicial"))

    def entrada_stock(self, codigo: str, cantidad: int, referencia: str = "") -> None:
        self._validar_codigo(codigo)
        self._stock[codigo] += cantidad
        self._kardex.append(MovimientoInventario(codigo, "ENTRADA", cantidad, referencia=referencia))

    def salida_stock(self, codigo: str, cantidad: int, referencia: str = "") -> None:
        self._validar_codigo(codigo)
        if self._stock[codigo] < cantidad:
            raise ValueError(f"Stock insuficiente de {codigo}: disponible {self._stock[codigo]}, solicitado {cantidad}")
        self._stock[codigo] -= cantidad
        self._kardex.append(MovimientoInventario(codigo, "SALIDA", cantidad, referencia=referencia))

    def consultar_stock(self, codigo: str) -> int:
        self._validar_codigo(codigo)
        return self._stock[codigo]

    def hay_disponibilidad(self, codigo: str, cantidad: int) -> bool:
        return self.consultar_stock(codigo) >= cantidad

    def productos_bajo_minimo(self) -> List[Producto]:
        return [p for c, p in self._productos.items() if self._stock[c] < p.stock_minimo]

    def kardex_producto(self, codigo: str) -> List[MovimientoInventario]:
        return [m for m in self._kardex if m.producto_codigo == codigo]

    def obtener_producto(self, codigo: str) -> Producto:
        self._validar_codigo(codigo)
        return self._productos[codigo]

    def _validar_codigo(self, codigo: str) -> None:
        if codigo not in self._productos:
            raise KeyError(f"Producto no registrado: {codigo}")
