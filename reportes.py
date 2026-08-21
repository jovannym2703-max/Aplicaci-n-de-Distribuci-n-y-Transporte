"""
Módulo: Reportes e Indicadores (KPI)
Calcula métricas clave a partir de los demás módulos: nivel de
servicio, costo promedio de envío y utilización de flota.
"""

from typing import List

from modelos import EstadoPedido
from pedidos import GestionPedidos
from transporte import GestionTransporte


def nivel_servicio(gestion_pedidos: GestionPedidos) -> float:
    """% de pedidos entregados sobre el total de pedidos no cancelados."""
    entregados = len(gestion_pedidos.listar_por_estado(EstadoPedido.ENTREGADO))
    cancelados = len(gestion_pedidos.listar_por_estado(EstadoPedido.CANCELADO))
    total = len(gestion_pedidos._pedidos)  # uso interno con fines de reporte
    base = total - cancelados
    return round((entregados / base) * 100, 2) if base else 0.0


def costo_promedio_envio(rutas: List) -> float:
    if not rutas:
        return 0.0
    return round(sum(r.costo_estimado for r in rutas) / len(rutas), 2)


def utilizacion_flota(gestion_transporte: GestionTransporte) -> float:
    """% de vehículos de la flota actualmente en uso (no disponibles)."""
    flota = list(gestion_transporte._flota.values())
    if not flota:
        return 0.0
    en_uso = len([v for v in flota if not v.disponible])
    return round((en_uso / len(flota)) * 100, 2)
