"""
Módulo: Gestión de Inventario
==============================
Controla existencias de productos, movimientos (kardex) y alertas de
stock mínimo, e incorpora modelos clásicos de gestión de inventarios
usados en la literatura de operaciones:

- Cantidad Económica de Pedido (EOQ / modelo de Wilson):
      EOQ = sqrt( 2 * D * S / H )
  donde D = demanda anual, S = costo de ordenar, H = costo de mantener
  una unidad en inventario durante un año (H = i * costo_unitario).

- Punto de Reorden (ROP):
      ROP = demanda_diaria_promedio * lead_time_dias + stock_seguridad

- Clasificación ABC por valor de consumo anual (regla 80/15/5).

- Rotación de inventario e indicadores de valorización.
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import sqrt
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

    # ------------------------------------------------------------------
    # Operaciones básicas de inventario
    # ------------------------------------------------------------------
    def registrar_producto(self, producto: Producto, stock_inicial: int = 0) -> None:
        self._productos[producto.codigo] = producto
        self._stock[producto.codigo] = stock_inicial
        if stock_inicial:
            self._kardex.append(MovimientoInventario(producto.codigo, "ENTRADA", stock_inicial, referencia="Stock inicial"))

    def entrada_stock(self, codigo: str, cantidad: int, referencia: str = "") -> None:
        self._validar_codigo(codigo)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
        self._stock[codigo] += cantidad
        self._kardex.append(MovimientoInventario(codigo, "ENTRADA", cantidad, referencia=referencia))

    def salida_stock(self, codigo: str, cantidad: int, referencia: str = "") -> None:
        self._validar_codigo(codigo)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
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

    def productos_bajo_punto_reorden(self) -> List[Producto]:
        return [p for c, p in self._productos.items() if self._stock[c] <= self.calcular_punto_reorden(c)]

    def kardex_producto(self, codigo: str) -> List[MovimientoInventario]:
        return [m for m in self._kardex if m.producto_codigo == codigo]

    def obtener_producto(self, codigo: str) -> Producto:
        self._validar_codigo(codigo)
        return self._productos[codigo]

    def listar_productos(self) -> List[Producto]:
        return list(self._productos.values())

    # ------------------------------------------------------------------
    # Modelos de gestión de inventarios (literatura de operaciones)
    # ------------------------------------------------------------------
    def calcular_eoq(self, codigo: str) -> float:
        """Cantidad Económica de Pedido (modelo de Wilson).

        EOQ = sqrt(2 * D * S / H)
        D: demanda anual estimada (demanda_diaria_promedio * 365)
        S: costo de ordenar por pedido
        H: costo de mantener una unidad en inventario por año
        """
        p = self.obtener_producto(codigo)
        demanda_anual = p.demanda_diaria_promedio * 365
        if demanda_anual <= 0 or p.costo_unitario <= 0:
            return 0.0
        costo_mantenimiento_unitario = p.costo_unitario * p.tasa_mantenimiento_anual
        if costo_mantenimiento_unitario <= 0:
            return 0.0
        eoq = sqrt((2 * demanda_anual * p.costo_pedido) / costo_mantenimiento_unitario)
        return round(eoq, 0)

    def calcular_punto_reorden(self, codigo: str) -> float:
        """ROP = demanda diaria promedio * lead time (días) + stock de seguridad."""
        p = self.obtener_producto(codigo)
        return round(p.demanda_diaria_promedio * p.lead_time_dias + p.stock_seguridad, 1)

    def calcular_numero_pedidos_anuales(self, codigo: str) -> float:
        p = self.obtener_producto(codigo)
        eoq = self.calcular_eoq(codigo)
        demanda_anual = p.demanda_diaria_promedio * 365
        if eoq <= 0:
            return 0.0
        return round(demanda_anual / eoq, 1)

    def costo_total_anual_inventario(self, codigo: str) -> float:
        """Costo total anual = costo de ordenar + costo de mantener, evaluado en el EOQ."""
        p = self.obtener_producto(codigo)
        eoq = self.calcular_eoq(codigo)
        demanda_anual = p.demanda_diaria_promedio * 365
        if eoq <= 0:
            return 0.0
        costo_ordenar = (demanda_anual / eoq) * p.costo_pedido
        costo_mantener = (eoq / 2) * (p.costo_unitario * p.tasa_mantenimiento_anual)
        return round(costo_ordenar + costo_mantener, 0)

    def clasificar_abc(self) -> Dict[str, str]:
        """Clasificación ABC por valor de consumo anual (regla 80/15/5).

        A: productos que acumulan ~80% del valor de consumo anual.
        B: siguiente ~15%.
        C: el 5% restante.
        Actualiza el atributo `clasificacion_abc` de cada Producto y
        retorna el diccionario código -> clase.
        """
        if not self._productos:
            return {}

        valores = {
            codigo: prod.demanda_diaria_promedio * 365 * prod.costo_unitario
            for codigo, prod in self._productos.items()
        }
        valor_total = sum(valores.values())
        resultado: Dict[str, str] = {}

        if valor_total <= 0:
            for codigo, prod in self._productos.items():
                prod.clasificacion_abc = "C"
                resultado[codigo] = "C"
            return resultado

        ordenados = sorted(valores.items(), key=lambda kv: kv[1], reverse=True)
        acumulado = 0.0
        for codigo, valor in ordenados:
            acumulado += valor
            porcentaje_acumulado = acumulado / valor_total
            if porcentaje_acumulado <= 0.80:
                clase = "A"
            elif porcentaje_acumulado <= 0.95:
                clase = "B"
            else:
                clase = "C"
            self._productos[codigo].clasificacion_abc = clase
            resultado[codigo] = clase
        return resultado

    def rotacion_inventario(self, codigo: str) -> float:
        """Rotación anual aproximada = salidas acumuladas / stock promedio actual."""
        self._validar_codigo(codigo)
        salidas = sum(m.cantidad for m in self._kardex if m.producto_codigo == codigo and m.tipo == "SALIDA")
        stock_actual = max(self._stock[codigo], 1)
        return round(salidas / stock_actual, 2)

    def valor_inventario_total(self) -> float:
        return round(sum(self._stock[c] * p.costo_unitario for c, p in self._productos.items()), 0)

    def dias_inventario_disponible(self, codigo: str) -> float:
        """Días de cobertura del stock actual dada la demanda diaria promedio."""
        p = self.obtener_producto(codigo)
        if p.demanda_diaria_promedio <= 0:
            return float("inf")
        return round(self._stock[codigo] / p.demanda_diaria_promedio, 1)

    # ------------------------------------------------------------------
    def _validar_codigo(self, codigo: str) -> None:
        if codigo not in self._productos:
            raise KeyError(f"Producto no registrado: {codigo}")
