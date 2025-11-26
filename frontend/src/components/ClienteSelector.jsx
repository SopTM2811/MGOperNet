import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Plus, User, Mail, Phone, MessageCircle, Percent, X, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ClienteSelector = ({ onClienteSeleccionado, clienteSeleccionado }) => {
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [buscando, setB uscando] = useState(false);
  const [clientes, setClientes] = useState([]);
  const [busqueda, setBusqueda] = useState('');
  const [creando, setCreando] = useState(false);
  
  // Formulario de nuevo cliente
  const [nuevoCliente, setNuevoCliente] = useState({
    nombre: '',
    email: '',
    pais: 'MX',
    prefijo_telefono: '+52',
    telefono: '',
    telegram_id: '',
    porcentaje_comision_cliente: 0.65,
    canal_preferido: 'WhatsApp',
    propietario: 'D'
  });

  useEffect(() => {
    buscarClientes('');
  }, []);

  const buscarClientes = async (termino) => {
    try {
      setBuscando(true);
      const response = await axios.get(`${API}/clientes/buscar`, {
        params: { q: termino }
      });
      setClientes(response.data);
    } catch (error) {
      console.error('Error buscando clientes:', error);
    } finally {
      setBuscando(false);
    }
  };

  const handleBusquedaChange = (e) => {
    const valor = e.target.value;
    setBusqueda(valor);
    buscarClientes(valor);
  };

  const handleSeleccionarCliente = (cliente) => {
    onClienteSeleccionado(cliente);
  };

  const handleCrearCliente = async (e) => {
    e.preventDefault();
    
    try {
      setCreando(true);
      const response = await axios.post(`${API}/clientes`, nuevoCliente);
      
      toast.success('Cliente creado exitosamente');
      
      // Seleccionar el cliente recién creado
      onClienteSeleccionado(response.data);
      
      // Cerrar formulario
      setMostrarFormulario(false);
      
      // Resetear formulario
      setNuevoCliente({
        nombre: '',
        email: '',
        pais: 'MX',
        prefijo_telefono: '+52',
        telefono: '',
        telegram_id: '',
        porcentaje_comision_cliente: 0.65,
        canal_preferido: 'WhatsApp',
        propietario: 'D'
      });
      
      // Recargar lista de clientes
      buscarClientes('');
    } catch (error) {
      console.error('Error creando cliente:', error);
      toast.error(error.response?.data?.detail || 'Error al crear cliente');
    } finally {
      setCreando(false);
    }
  };

  const prefijos = [
    { pais: 'MX', nombre: 'México', prefijo: '+52' },
    { pais: 'US', nombre: 'Estados Unidos', prefijo: '+1' },
    { pais: 'CO', nombre: 'Colombia', prefijo: '+57' },
    { pais: 'ES', nombre: 'España', prefijo: '+34' },
    { pais: 'AR', nombre: 'Argentina', prefijo: '+54' },
  ];

  if (clienteSeleccionado) {
    // Mostrar cliente seleccionado
    return (
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="bg-blue-600 rounded-full p-2">
              <User className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="font-semibold text-lg">{clienteSeleccionado.nombre}</p>
              <Badge variant="secondary" className="mt-1">
                Cliente Seleccionado
              </Badge>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onClienteSeleccionado(null)}
            data-testid="deselect-client-btn"
          >
            Cambiar
          </Button>
        </div>
        
        <div className="grid md:grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2 text-slate-700">
            <Mail className="h-4 w-4 text-blue-600" />
            <span>{clienteSeleccionado.email}</span>
          </div>
          
          <div className="flex items-center gap-2 text-slate-700">
            <Phone className="h-4 w-4 text-blue-600" />
            <span>{clienteSeleccionado.telefono_completo || `${clienteSeleccionado.prefijo_telefono}${clienteSeleccionado.telefono}`}</span>
          </div>
          
          {clienteSeleccionado.telegram_id && (
            <div className="flex items-center gap-2 text-slate-700">
              <MessageCircle className="h-4 w-4 text-blue-600" />
              <span>{clienteSeleccionado.telegram_id}</span>
            </div>
          )}
          
          <div className="flex items-center gap-2 text-slate-700">
            <Percent className="h-4 w-4 text-blue-600" />
            <span>Comisión: {clienteSeleccionado.porcentaje_comision_cliente}%</span>
          </div>
        </div>
      </Card>
    );
  }

  if (mostrarFormulario) {
    // Formulario de crear nuevo cliente
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Crear Nuevo Cliente</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMostrarFormulario(false)}
            data-testid="cancel-new-client-btn"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <form onSubmit={handleCrearCliente} className="space-y-4">
          <div>
            <Label htmlFor="nombre">Nombre del Cliente *</Label>
            <Input
              id="nombre"
              value={nuevoCliente.nombre}
              onChange={(e) => setNuevoCliente({...nuevoCliente, nombre: e.target.value})}
              placeholder="Nombre completo"
              required
              data-testid="new-client-name-input"
            />
          </div>

          <div>
            <Label htmlFor="email">Correo Electrónico *</Label>
            <Input
              id="email"
              type="email"
              value={nuevoCliente.email}
              onChange={(e) => setNuevoCliente({...nuevoCliente, email: e.target.value})}
              placeholder="email@ejemplo.com"
              required
              data-testid="new-client-email-input"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <Label>País / Prefijo *</Label>
              <Select
                value={nuevoCliente.pais}
                onValueChange={(value) => {
                  const prefijoObj = prefijos.find(p => p.pais === value);
                  setNuevoCliente({
                    ...nuevoCliente,
                    pais: value,
                    prefijo_telefono: prefijoObj?.prefijo || '+52'
                  });
                }}
              >
                <SelectTrigger data-testid="new-client-country-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {prefijos.map(p => (
                    <SelectItem key={p.pais} value={p.pais}>
                      {p.nombre} ({p.prefijo})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="telefono">Teléfono / WhatsApp *</Label>
              <div className="flex gap-2">
                <Input
                  value={nuevoCliente.prefijo_telefono}
                  readOnly
                  className="w-20"
                />
                <Input
                  id="telefono"
                  type="tel"
                  value={nuevoCliente.telefono}
                  onChange={(e) => setNuevoCliente({...nuevoCliente, telefono: e.target.value})}
                  placeholder="3312345678"
                  required
                  data-testid="new-client-phone-input"
                  className="flex-1"
                />
              </div>
            </div>
          </div>

          <div>
            <Label htmlFor="telegram_id">Telegram ID (opcional)</Label>
            <Input
              id="telegram_id"
              value={nuevoCliente.telegram_id}
              onChange={(e) => setNuevoCliente({...nuevoCliente, telegram_id: e.target.value})}
              placeholder="@usuario o ID numérico"
              data-testid="new-client-telegram-input"
            />
          </div>

          <div>
            <Label htmlFor="comision">Comisión del Cliente (%) *</Label>
            <Input
              id="comision"
              type="number"
              step="0.01"
              min="0"
              value={nuevoCliente.porcentaje_comision_cliente}
              onChange={(e) => setNuevoCliente({...nuevoCliente, porcentaje_comision_cliente: parseFloat(e.target.value)})}
              required
              data-testid="new-client-commission-input"
            />
            <p className="text-xs text-slate-500 mt-1">
              Ejemplo: 0.65 para 0.65%, o 1.0 para 1.0%
            </p>
          </div>

          <div>
            <Label>Canal Preferido</Label>
            <Select
              value={nuevoCliente.canal_preferido}
              onValueChange={(value) => setNuevoCliente({...nuevoCliente, canal_preferido: value})}
            >
              <SelectTrigger data-testid="new-client-channel-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="WhatsApp">WhatsApp</SelectItem>
                <SelectItem value="Telegram">Telegram</SelectItem>
                <SelectItem value="Correo">Correo</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Propietario *</Label>
            <Select
              value={nuevoCliente.propietario}
              onValueChange={(value) => setNuevoCliente({...nuevoCliente, propietario: value})}
            >
              <SelectTrigger data-testid="new-client-owner-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="D">Daniel</SelectItem>
                <SelectItem value="S">Samuel</SelectItem>
                <SelectItem value="R">Ramón</SelectItem>
                <SelectItem value="M">MBco / Market Business</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setMostrarFormulario(false)}
              className="flex-1"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={creando}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
              data-testid="create-client-btn"
            >
              {creando ? 'Creando...' : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Crear Cliente
                </>
              )}
            </Button>
          </div>
        </form>
      </Card>
    );
  }

  // Vista de búsqueda/selección
  return (
    <Card className="p-4">
      <div className="mb-4">
        <Label>Seleccionar Cliente</Label>
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por nombre, email o teléfono..."
            value={busqueda}
            onChange={handleBusquedaChange}
            className="pl-10"
            data-testid="search-client-input"
          />
        </div>
      </div>

      <Button
        onClick={() => setMostrarFormulario(true)}
        variant="outline"
        className="w-full mb-4 border-dashed border-2 hover:bg-blue-50 hover:border-blue-400"
        data-testid="show-new-client-form-btn"
      >
        <Plus className="h-4 w-4 mr-2" />
        Crear Nuevo Cliente NetCash
      </Button>

      {buscando ? (
        <div className="text-center py-4 text-slate-500">Buscando...</div>
      ) : clientes.length === 0 ? (
        <div className="text-center py-4 text-slate-500">
          No se encontraron clientes
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {clientes.map((cliente) => (
            <div
              key={cliente.id}
              className="p-3 border rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"
              onClick={() => handleSeleccionarCliente(cliente)}
              data-testid={`client-option-${cliente.id}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="font-medium">{cliente.nombre}</p>
                  <div className="text-xs text-slate-600 mt-1 space-y-0.5">
                    <p>{cliente.email}</p>
                    <p>{cliente.telefono_completo || `${cliente.prefijo_telefono}${cliente.telefono}`}</p>
                    {cliente.telegram_id && <p>Telegram: {cliente.telegram_id}</p>}
                  </div>
                </div>
                <Badge variant="secondary" className="text-xs">
                  {cliente.porcentaje_comision_cliente}%
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

export default ClienteSelector;