import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Plus, Search, Home as HomeIcon, User, Edit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import NuevoClienteModal from '@/components/NuevoClienteModal';
import EditarClienteModal from '@/components/EditarClienteModal';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Clientes = () => {
  const navigate = useNavigate();
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showNuevoCliente, setShowNuevoCliente] = useState(false);
  const [showEditarCliente, setShowEditarCliente] = useState(false);
  const [clienteSeleccionado, setClienteSeleccionado] = useState(null);

  useEffect(() => {
    cargarClientes();
  }, []);

  const cargarClientes = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/clientes`);
      setClientes(response.data);
    } catch (error) {
      console.error('Error cargando clientes:', error);
      toast.error('Error al cargar clientes');
    } finally {
      setLoading(false);
    }
  };

  const clientesFiltrados = clientes.filter(cliente => 
    cliente.nombre.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (cliente.telefono && cliente.telefono.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (cliente.rfc && cliente.rfc.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (cliente.email && cliente.email.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const formatFecha = (fecha) => {
    if (!fecha) return '-';
    const date = new Date(fecha);
    return date.toLocaleDateString('es-MX', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  const getPropietarioBadge = (propietario) => {
    const propietarioMap = {
      'M': { label: 'MBco', className: 'bg-blue-100 text-blue-800' },
      'D': { label: 'Daniel', className: 'bg-purple-100 text-purple-800' },
      'S': { label: 'Samuel', className: 'bg-green-100 text-green-800' },
      'R': { label: 'Ramón', className: 'bg-orange-100 text-orange-800' }
    };
    
    const config = propietarioMap[propietario] || { label: propietario, className: 'bg-gray-100 text-gray-800' };
    
    return (
      <Badge className={config.className}>
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="min-h-screen bg-white py-4 sm:py-8">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header - Mismo diseño que Dashboard */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 sm:mb-12">
          <div>
            <h1 
              className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-1 sm:mb-2 tracking-tight"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Clientes NetCash
            </h1>
            <p className="text-sm sm:text-base text-slate-600 font-light">Gestión de clientes y sus operaciones</p>
          </div>
          <div className="flex flex-wrap gap-2 sm:gap-3">
            <Button
              variant="outline"
              onClick={() => navigate('/')}
              className="border-slate-300 text-sm"
              size="sm"
            >
              <HomeIcon className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Inicio</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/dashboard')}
              className="border-slate-300 text-sm"
              size="sm"
            >
              <span className="hidden sm:inline">Dashboard</span>
              <span className="sm:hidden">Dash</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/alta-cliente-telegram')}
              className="border-slate-300 text-sm"
              size="sm"
            >
              <User className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Alta Telegram</span>
            </Button>
            <Button
              onClick={() => setShowNuevoCliente(true)}
              className="bg-blue-600 hover:bg-blue-700 text-sm"
              size="sm"
            >
              <Plus className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Nuevo Cliente</span>
              <span className="sm:hidden">Nuevo</span>
            </Button>
          </div>
        </div>

        {/* Search */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-4 w-4" />
              <Input
                placeholder="Buscar por nombre, teléfono, RFC o email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
          </CardContent>
        </Card>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Total Clientes</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{clientes.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Pendiente Validación</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-yellow-600">
                {clientes.filter(c => c.estado === 'pendiente_validacion').length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Activos</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-600">
                {clientes.filter(c => c.activo && c.estado === 'activo').length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Con Telegram</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600">
                {clientes.filter(c => c.telegram_id).length}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Clients List */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-600">Cargando clientes...</p>
          </div>
        ) : clientesFiltrados.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <User className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600">
                {searchTerm ? 'No se encontraron clientes' : 'No hay clientes registrados'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {clientesFiltrados.map((cliente) => (
              <Card key={cliente.id} className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      {/* Header con nombre y badges - ORDEN FIJO */}
                      <div className="flex items-center gap-3 mb-3">
                        <h3 className="text-lg font-semibold">{cliente.nombre}</h3>
                        {cliente.estado === 'pendiente_validacion' && (
                          <Badge className="bg-yellow-100 text-yellow-800">Pendiente Validación</Badge>
                        )}
                        {cliente.estado === 'activo' && (
                          <Badge className="bg-green-100 text-green-800">Activo</Badge>
                        )}
                        {!cliente.activo && (
                          <Badge variant="secondary">Inactivo</Badge>
                        )}
                        {getPropietarioBadge(cliente.propietario)}
                      </div>
                      
                      {/* Alerta de comisión pendiente */}
                      {(cliente.porcentaje_comision_cliente === null || cliente.porcentaje_comision_cliente === 0) && (
                        <div className="mb-3 p-2 bg-amber-50 border-l-4 border-amber-400 text-sm text-amber-800">
                          ⚠️ Pendiente: Definir comisión por Ana
                        </div>
                      )}
                      
                      {/* Datos del cliente - ORDEN FIJO */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-slate-600">
                        {/* Fila 1: Teléfono y Email */}
                        <div className="flex items-center gap-2">
                          <span className="font-medium">📱</span>
                          <span>{cliente.telefono_completo || 'Sin teléfono'}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">📧</span>
                          <span>{cliente.email || 'Sin correo'}</span>
                        </div>
                        
                        {/* Fila 2: Fecha de alta y Comisión */}
                        <div className="flex items-center gap-2">
                          <span className="font-medium">📅</span>
                          <span>Alta: {formatFecha(cliente.fecha_alta)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">💰</span>
                          <span>
                            Comisión: {
                              cliente.porcentaje_comision_cliente === null 
                                ? '❌ Pendiente' 
                                : `${cliente.porcentaje_comision_cliente}%`
                            }
                          </span>
                        </div>
                        
                        {/* Fila 3: RFC y Telegram */}
                        {cliente.rfc && (
                          <div className="flex items-center gap-2">
                            <span className="font-medium">🆔</span>
                            <span>{cliente.rfc}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          <span className="font-medium">✈️</span>
                          <span>
                            {cliente.telegram_id ? '✅ Telegram conectado' : '⚪ Sin Telegram'}
                          </span>
                        </div>
                      </div>

                      {cliente.notas && (
                        <div className="mt-3 p-3 bg-slate-50 rounded-lg text-sm text-slate-600">
                          <span className="font-medium">Notas:</span> {cliente.notas}
                        </div>
                      )}
                    </div>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setClienteSeleccionado(cliente);
                        setShowEditarCliente(true);
                      }}
                      className="shrink-0 ml-4"
                    >
                      <Edit className="h-4 w-4 mr-2" />
                      Editar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Modales */}
      {showNuevoCliente && (
        <NuevoClienteModal
          onClose={() => setShowNuevoCliente(false)}
          onSuccess={cargarClientes}
        />
      )}
      
      {showEditarCliente && clienteSeleccionado && (
        <EditarClienteModal
          cliente={clienteSeleccionado}
          onClose={() => {
            setShowEditarCliente(false);
            setClienteSeleccionado(null);
          }}
          onSuccess={cargarClientes}
        />
      )}
    </div>
  );
};

export default Clientes;
