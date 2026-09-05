"""
Módulo: Reportes e Indicadores (KPI)
======================================
Calcula métricas clave a partir de los demás módulos, alineadas con los
indicadores estándar de gestión logística y de operaciones:

- Nivel de servicio (% pedidos entregados sobre pedidos no cancelados).
- OTIF (On Time In Full): combina entregas a tiempo (pedidos.py) con
  el fill rate (pedidos completos sin backorder).
- Costo logístico: promedio por envío, por kilómetro y por kilogramo
  transportado.
- Utilización de flota: por número de vehículos y por capacidad
  (peso/volumen) realmente aprovechada en las rutas calculadas.
- Rotación de inventario y valor de inventario inmovilizado.
"""

from typing import List

from modelos import EstadoPedido, Ruta
from pedidos import GestionPedidos
from transporte import GestionTransporte
from inventario import GestionInventario


def nivel_servicio(gestion_pedidos: GestionPedidos) -> float:
    """% de pedidos entregados sobre el total de pedidos no cancelados."""
    entregados = len(gestion_pedidos.listar_por_estado(EstadoPedido.ENTREGADO))
    cancelados = len(gestion_pedidos.listar_por_estado(EstadoPedido.CANCELADO))
    total = len(gestion_pedidos._pedidos)  # uso interno con fines de reporte
    base = total - cancelados
    return round((entregados / base) * 100, 2) if base else 0.0


def costo_promedio_envio(rutas: List[Ruta]) -> float:
    if not rutas:
        return 0.0
    return round(sum(r.costo_estimado for r in rutas) / len(rutas), 2)


def costo_por_km(rutas: List[Ruta]) -> float:
    distancia_total = sum(r.distancia_km for r in rutas)
    if distancia_total <= 0:
        return 0.0
    costo_total = sum(r.costo_estimado for r in rutas)
    return round(costo_total / distancia_total, 2)


def costo_por_kg_transportado(rutas: List[Ruta]) -> float:
    peso_total = sum(r.peso_total_kg for r in rutas)
    if peso_total <= 0:
        return 0.0
    costo_total = sum(r.costo_estimado for r in rutas)
    return round(costo_total / peso_total, 2)


def utilizacion_flota(gestion_transporte: GestionTransporte) -> float:
    """% de vehículos de la flota actualmente en uso (no disponibles)."""
    flota = list(gestion_transporte._flota.values())
    if not flota:
        return 0.0
    en_uso = len([v for v in flota if not v.disponible])
    return round((en_uso / len(flota)) * 100, 2)


def utilizacion_capacidad_flota(rutas: List[Ruta]) -> float:
    """% promedio de aprovechamiento de capacidad (peso) en las rutas
    calculadas — indicador más fino que el conteo simple de vehículos."""
    if not rutas:
        return 0.0
    return round(sum(r.utilizacion_peso for r in rutas) / len(rutas), 1)


def otif(gestion_pedidos: GestionPedidos) -> float:
    """OTIF (On Time In Full): aproxima el porcentaje de pedidos entregados
    a tiempo Y sin haber pasado por backorder, sobre el total de pedidos
    ya gestionados (no CREADO)."""
    a_tiempo = gestion_pedidos.tasa_entregas_a_tiempo() / 100
    completos = gestion_pedidos.fill_rate() / 100
    return round(a_tiempo * completos * 100, 1)


def rotacion_inventario_promedio(gestion_inventario: GestionInventario) -> float:
    productos = gestion_inventario.listar_productos()
    if not productos:
        return 0.0
    rotaciones = [gestion_inventario.rotacion_inventario(p.codigo) for p in productos]
    return round(sum(rotaciones) / len(rotaciones), 2)


def valor_inventario_inmovilizado(gestion_inventario: GestionInventario) -> float:
    return gestion_inventario.valor_inventario_total()
