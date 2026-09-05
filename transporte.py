"""
Módulo: Gestión de Transporte
Administra la flota de vehículos, asigna pedidos según capacidad y
calcula rutas mediante una heurística del vecino más cercano.
"""

import math
from datetime import datetime
from typing import Dict, List, Tuple

from modelos import Conductor, EstadoMantenimiento, Mantenimiento, Pedido, Ruta, Vehiculo


class GestionTransporte:
    def __init__(self):
        self._flota: Dict[str, Vehiculo] = {}
        self._conductores: Dict[str, Conductor] = {}
        self._mantenimientos: Dict[str, Mantenimiento] = {}
        self._rutas: Dict[str, Ruta] = {}
        self._contador = 0
        self._contador_mant = 0

    # --- Gestión de flota ---
    def registrar_vehiculo(self, vehiculo: Vehiculo) -> None:
        self._flota[vehiculo.placa] = vehiculo

    def vehiculos_disponibles(self) -> List[Vehiculo]:
        return [v for v in self._flota.values() if v.disponible]

    def liberar_vehiculo(self, placa: str) -> None:
        self._flota[placa].disponible = True

    # --- Gestión de conductores ---
    def registrar_conductor(self, conductor: Conductor) -> None:
        self._conductores[conductor.id] = conductor

    def conductores_disponibles(self) -> List[Conductor]:
        return [c for c in self._conductores.values() if c.disponible]

    # --- Gestión de mantenimiento ---
    def programar_mantenimiento(self, placa: str, tipo: str, inicio: datetime,
                                 fin: datetime, notas: str = "") -> Mantenimiento:
        self._contador_mant += 1
        mant = Mantenimiento(
            id=f"MAN-{self._contador_mant:04d}",
            vehiculo=self._flota[placa],
            tipo=tipo, inicio=inicio, fin=fin, notas=notas,
        )
        self._mantenimientos[mant.id] = mant
        self._flota[placa].disponible = False
        return mant

    def completar_mantenimiento(self, mant_id: str) -> None:
        mant = self._mantenimientos[mant_id]
        mant.estado = EstadoMantenimiento.COMPLETADO
        mant.vehiculo.disponible = True

    def listar_mantenimientos(self) -> List[Mantenimiento]:
        return list(self._mantenimientos.values())

    # --- Asignación de pedidos a un vehículo (bin-packing simple por capacidad) ---
    def asignar_pedidos_a_vehiculo(self, pedidos: List[Pedido], vehiculo: Vehiculo) -> Tuple[List[Pedido], List[Pedido]]:
        """Devuelve (asignados, no_asignados) respetando peso y volumen del vehículo."""
        asignados: List[Pedido] = []
        peso_acum = volumen_acum = 0.0
        no_asignados: List[Pedido] = []
        for pedido in sorted(pedidos, key=lambda p: p.peso_total, reverse=True):
            if (peso_acum + pedido.peso_total <= vehiculo.capacidad_peso_kg and
                    volumen_acum + pedido.volumen_total <= vehiculo.capacidad_volumen_m3):
                asignados.append(pedido)
                peso_acum += pedido.peso_total
                volumen_acum += pedido.volumen_total
            else:
                no_asignados.append(pedido)
        return asignados, no_asignados

    # --- Planificación de ruta (heurística del vecino más cercano) ---
    def calcular_ruta_optima(self, origen: Tuple[float, float], vehiculo: Vehiculo,
                              pedidos: List[Pedido]) -> Ruta:
        self._contador += 1
        pendientes = pedidos.copy()
        secuencia: List[Pedido] = []
        punto_actual = origen
        distancia_total = 0.0

        while pendientes:
            siguiente = min(pendientes, key=lambda p: self._distancia(punto_actual, p.cliente.coordenadas))
            distancia_total += self._distancia(punto_actual, siguiente.cliente.coordenadas)
            punto_actual = siguiente.cliente.coordenadas
            secuencia.append(siguiente)
            pendientes.remove(siguiente)

        # regreso al origen (round trip)
        distancia_total += self._distancia(punto_actual, origen)

        costo = vehiculo.costo_fijo + distancia_total * vehiculo.costo_km
        ruta = Ruta(
            id=f"RUT-{self._contador:04d}",
            vehiculo=vehiculo,
            origen=origen,
            secuencia_pedidos=secuencia,
            distancia_km=round(distancia_total, 2),
            costo_estimado=round(costo, 2),
        )
        self._rutas[ruta.id] = ruta
        vehiculo.disponible = False
        return ruta

    def obtener_ruta(self, ruta_id: str) -> Ruta:
        return self._rutas[ruta_id]

    @staticmethod
    def _distancia(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.dist(a, b)
