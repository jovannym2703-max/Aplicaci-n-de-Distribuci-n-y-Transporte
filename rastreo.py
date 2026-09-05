"""
Módulo: Rastreo y Trazabilidad
================================
Crea envíos a partir de una ruta y registra el historial de estados
(pendiente, en ruta, entregado, incidencia) con marca de tiempo.

Se incorpora el cálculo de ETA (tiempo estimado de llegada) a partir del
tiempo estimado de la ruta, el registro de la posición aproximada del
vehículo a lo largo del recorrido (interpolación lineal sobre la
secuencia de paradas) y el registro estructurado de incidencias, todo
insumo estándar de un módulo de "track & trace" en distribución.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from modelos import Envio, EstadoEnvio, Ruta


class GestionRastreo:
    def __init__(self):
        self._envios: Dict[str, Envio] = {}
        self._contador = 0

    def crear_envio(self, ruta: Ruta) -> Envio:
        self._contador += 1
        eta = datetime.now() + timedelta(hours=ruta.tiempo_estimado_horas) if ruta.tiempo_estimado_horas else None
        envio = Envio(
            id=f"ENV-{self._contador:04d}",
            ruta=ruta,
            eta=eta,
            ubicacion_actual=ruta.origen,
            porcentaje_avance=0.0,
        )
        envio.historial.append((datetime.now(), EstadoEnvio.PENDIENTE, "Envío creado, pendiente de despacho"))
        self._envios[envio.id] = envio
        return envio

    def actualizar_estado(self, envio_id: str, estado: EstadoEnvio, nota: str = "") -> Envio:
        envio = self._obtener(envio_id)
        envio.estado = estado
        if estado == EstadoEnvio.ENTREGADO:
            envio.porcentaje_avance = 100.0
            envio.ubicacion_actual = envio.ruta.origen if not envio.ruta.secuencia_pedidos else envio.ruta.secuencia_pedidos[-1].cliente.coordenadas
        envio.historial.append((datetime.now(), estado, nota))
        return envio

    def avanzar_envio(self, envio_id: str, porcentaje: float) -> Envio:
        """Actualiza el porcentaje de avance del envío e interpola su
        ubicación aproximada sobre la secuencia de paradas de la ruta."""
        envio = self._obtener(envio_id)
        porcentaje = max(0.0, min(100.0, porcentaje))
        envio.porcentaje_avance = porcentaje
        envio.ubicacion_actual = self._interpolar_ubicacion(envio.ruta, porcentaje)
        if envio.estado == EstadoEnvio.PENDIENTE and porcentaje > 0:
            envio.estado = EstadoEnvio.EN_RUTA
            envio.historial.append((datetime.now(), EstadoEnvio.EN_RUTA, "Vehículo despachado"))
        return envio

    def registrar_incidencia(self, envio_id: str, descripcion: str) -> Envio:
        return self.actualizar_estado(envio_id, EstadoEnvio.INCIDENCIA, descripcion)

    def consultar_estado(self, envio_id: str) -> EstadoEnvio:
        return self._obtener(envio_id).estado

    def historial(self, envio_id: str) -> List:
        return self._obtener(envio_id).historial

    def listar_envios(self) -> List[Envio]:
        return list(self._envios.values())

    def obtener_envio(self, envio_id: str) -> Envio:
        return self._obtener(envio_id)

    # ------------------------------------------------------------------
    @staticmethod
    def _interpolar_ubicacion(ruta: Ruta, porcentaje: float) -> Tuple[float, float]:
        puntos = [ruta.origen] + [p.cliente.coordenadas for p in ruta.secuencia_pedidos] + [ruta.origen]
        if len(puntos) < 2:
            return ruta.origen
        posicion_relativa = (porcentaje / 100.0) * (len(puntos) - 1)
        indice = min(int(posicion_relativa), len(puntos) - 2)
        fraccion = posicion_relativa - indice
        x0, y0 = puntos[indice]
        x1, y1 = puntos[indice + 1]
        return (round(x0 + (x1 - x0) * fraccion, 3), round(y0 + (y1 - y0) * fraccion, 3))

    def _obtener(self, envio_id: str) -> Envio:
        if envio_id not in self._envios:
            raise KeyError(f"Envío no encontrado: {envio_id}")
        return self._envios[envio_id]
