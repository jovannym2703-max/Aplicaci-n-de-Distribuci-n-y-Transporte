"""
Módulo: Gestión de Transporte
==============================
Administra la flota de vehículos y conductores, asigna pedidos según
capacidad (peso y volumen) y calcula rutas de reparto.

El ruteo se resuelve con una heurística de construcción (vecino más
cercano) seguida de una fase de mejora local (2-opt), que es el enfoque
clásico de dos etapas usado en la literatura del Problema de Ruteo de
Vehículos (VRP: Toth & Vigo, 2014) para obtener soluciones de buena
calidad con bajo costo computacional. También se ofrece asignación de
pedidos a múltiples vehículos de la flota (bin-packing por capacidad,
similar a un "First Fit Decreasing") para simular el despacho diario
completo en vez de un solo vehículo a la vez.
"""

import math
from datetime import datetime
from itertools import combinations
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

    def asignar_conductor(self, ruta_id: str, conductor_id: str) -> Ruta:
        ruta = self.obtener_ruta(ruta_id)
        conductor = self._conductores[conductor_id]
        ruta.conductor = conductor
        conductor.disponible = False
        return ruta

    def liberar_conductor(self, conductor_id: str) -> None:
        conductor = self._conductores[conductor_id]
        conductor.disponible = True
        conductor.viajes_completados += 1

    # --- Gestión de mantenimiento ---
    def programar_mantenimiento(self, placa: str, tipo: str, inicio: datetime,
                                 fin: datetime, notas: str = "", costo: float = 0.0) -> Mantenimiento:
        self._contador_mant += 1
        mant = Mantenimiento(
            id=f"MAN-{self._contador_mant:04d}",
            vehiculo=self._flota[placa],
            tipo=tipo, inicio=inicio, fin=fin, notas=notas, costo=costo,
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
        """Devuelve (asignados, no_asignados) respetando peso y volumen del
        vehículo. Los pedidos se ordenan primero por prioridad y luego por
        peso descendente (heurística First Fit Decreasing) para maximizar
        el aprovechamiento de la capacidad."""
        orden_prioridad = {"Urgente": 0, "Alta": 1, "Normal": 2, "Baja": 3}
        pedidos_ordenados = sorted(
            pedidos,
            key=lambda p: (orden_prioridad.get(getattr(p.prioridad, "value", p.prioridad), 2), -p.peso_total),
        )
        asignados: List[Pedido] = []
        peso_acum = volumen_acum = 0.0
        no_asignados: List[Pedido] = []
        for pedido in pedidos_ordenados:
            if (peso_acum + pedido.peso_total <= vehiculo.capacidad_peso_kg and
                    volumen_acum + pedido.volumen_total <= vehiculo.capacidad_volumen_m3):
                asignados.append(pedido)
                peso_acum += pedido.peso_total
                volumen_acum += pedido.volumen_total
            else:
                no_asignados.append(pedido)
        return asignados, no_asignados

    def asignar_pedidos_a_flota(self, pedidos: List[Pedido], vehiculos: List[Vehiculo]
                                 ) -> Dict[str, List[Pedido]]:
        """Distribuye un conjunto de pedidos entre varios vehículos
        disponibles, vehículo por vehículo (mayor capacidad primero),
        hasta agotar los pedidos o la capacidad de la flota. Retorna un
        diccionario placa -> lista de pedidos asignados."""
        pendientes = list(pedidos)
        vehiculos_ordenados = sorted(vehiculos, key=lambda v: v.capacidad_peso_kg, reverse=True)
        plan: Dict[str, List[Pedido]] = {}
        for vehiculo in vehiculos_ordenados:
            if not pendientes:
                break
            asignados, pendientes = self.asignar_pedidos_a_vehiculo(pendientes, vehiculo)
            if asignados:
                plan[vehiculo.placa] = asignados
        return plan

    # --- Planificación de ruta: vecino más cercano + mejora 2-opt ---
    def calcular_ruta_optima(self, origen: Tuple[float, float], vehiculo: Vehiculo,
                              pedidos: List[Pedido], aplicar_2opt: bool = True) -> Ruta:
        self._contador += 1
        secuencia = self._construir_vecino_mas_cercano(origen, pedidos)

        if aplicar_2opt and len(secuencia) >= 4:
            secuencia = self._mejorar_2opt(origen, secuencia)

        distancia_total = self._distancia_secuencia(origen, secuencia)
        costo = vehiculo.costo_fijo + distancia_total * vehiculo.costo_km
        tiempo_horas = (distancia_total / vehiculo.velocidad_promedio_kmh) if vehiculo.velocidad_promedio_kmh else 0.0
        # se añade un tiempo de servicio fijo de 10 minutos por parada de entrega
        tiempo_horas += len(secuencia) * (10 / 60)

        ruta = Ruta(
            id=f"RUT-{self._contador:04d}",
            vehiculo=vehiculo,
            origen=origen,
            secuencia_pedidos=secuencia,
            distancia_km=round(distancia_total, 2),
            costo_estimado=round(costo, 2),
            tiempo_estimado_horas=round(tiempo_horas, 2),
            algoritmo="Vecino más cercano + 2-opt" if aplicar_2opt else "Vecino más cercano",
        )
        self._rutas[ruta.id] = ruta
        vehiculo.disponible = False
        return ruta

    def _construir_vecino_mas_cercano(self, origen: Tuple[float, float], pedidos: List[Pedido]) -> List[Pedido]:
        pendientes = pedidos.copy()
        secuencia: List[Pedido] = []
        punto_actual = origen
        while pendientes:
            siguiente = min(pendientes, key=lambda p: self._distancia(punto_actual, p.cliente.coordenadas))
            punto_actual = siguiente.cliente.coordenadas
            secuencia.append(siguiente)
            pendientes.remove(siguiente)
        return secuencia

    def _mejorar_2opt(self, origen: Tuple[float, float], secuencia: List[Pedido], max_iter: int = 200) -> List[Pedido]:
        """Mejora local 2-opt: intercambia segmentos de la ruta si eso
        reduce la distancia total del recorrido (incluyendo el regreso al
        origen). Técnica estándar de mejora post-construcción en VRP."""
        mejor = secuencia[:]
        mejor_distancia = self._distancia_secuencia(origen, mejor)
        mejoro = True
        iteraciones = 0
        n = len(mejor)
        while mejoro and iteraciones < max_iter:
            mejoro = False
            iteraciones += 1
            for i, j in combinations(range(n), 2):
                if j - i < 1:
                    continue
                candidato = mejor[:i] + mejor[i:j + 1][::-1] + mejor[j + 1:]
                distancia_candidata = self._distancia_secuencia(origen, candidato)
                if distancia_candidata < mejor_distancia - 1e-9:
                    mejor = candidato
                    mejor_distancia = distancia_candidata
                    mejoro = True
        return mejor

    def _distancia_secuencia(self, origen: Tuple[float, float], secuencia: List[Pedido]) -> float:
        if not secuencia:
            return 0.0
        total = 0.0
        punto_actual = origen
        for pedido in secuencia:
            total += self._distancia(punto_actual, pedido.cliente.coordenadas)
            punto_actual = pedido.cliente.coordenadas
        total += self._distancia(punto_actual, origen)
        return total

    def obtener_ruta(self, ruta_id: str) -> Ruta:
        return self._rutas[ruta_id]

    def listar_rutas(self) -> List[Ruta]:
        return list(self._rutas.values())

    @staticmethod
    def _distancia(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.dist(a, b)
