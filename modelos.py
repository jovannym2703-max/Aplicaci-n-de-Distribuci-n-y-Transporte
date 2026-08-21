"""
Modelos de datos para el sistema de Gestión de Distribución y Transporte.
Contiene las entidades base usadas por todos los módulos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Tuple


class EstadoPedido(str, Enum):
    CREADO = "CREADO"
    CONFIRMADO = "CONFIRMADO"
    ASIGNADO = "ASIGNADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class EstadoEnvio(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_RUTA = "EN_RUTA"
    ENTREGADO = "ENTREGADO"
    INCIDENCIA = "INCIDENCIA"


@dataclass
class Producto:
    codigo: str
    nombre: str
    categoria: str
    peso_kg: float          # peso unitario
    volumen_m3: float       # volumen unitario
    stock_minimo: int = 0


@dataclass
class ItemPedido:
    producto: Producto
    cantidad: int

    @property
    def peso_total(self) -> float:
        return self.producto.peso_kg * self.cantidad

    @property
    def volumen_total(self) -> float:
        return self.producto.volumen_m3 * self.cantidad


@dataclass
class Cliente:
    nombre: str
    direccion: str
    coordenadas: Tuple[float, float]  # (x, y) — coordenadas planas simplificadas


@dataclass
class Pedido:
    id: str
    cliente: Cliente
    items: List[ItemPedido] = field(default_factory=list)
    estado: EstadoPedido = EstadoPedido.CREADO
    fecha_creacion: datetime = field(default_factory=datetime.now)

    @property
    def peso_total(self) -> float:
        return sum(i.peso_total for i in self.items)

    @property
    def volumen_total(self) -> float:
        return sum(i.volumen_total for i in self.items)


@dataclass
class Vehiculo:
    placa: str
    tipo: str                  # ej: "furgón", "camión", "moto"
    capacidad_peso_kg: float
    capacidad_volumen_m3: float
    costo_km: float            # costo variable por km
    costo_fijo: float = 0.0    # costo fijo de despacho
    disponible: bool = True


@dataclass
class Ruta:
    id: str
    vehiculo: Vehiculo
    origen: Tuple[float, float]
    secuencia_pedidos: List[Pedido] = field(default_factory=list)
    distancia_km: float = 0.0
    costo_estimado: float = 0.0


@dataclass
class Envio:
    id: str
    ruta: Ruta
    estado: EstadoEnvio = EstadoEnvio.PENDIENTE
    historial: List[Tuple[datetime, EstadoEnvio, str]] = field(default_factory=list)
