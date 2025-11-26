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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 shadow-sm">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <HomeIcon className="h-5 w-5 text-slate-600" />
              </button>
              <h1 className="text-2xl font-bold" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                Clientes NetCash
              </h1>
            </div>
            <Button
              onClick={() => setShowNuevoCliente(true)}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Nuevo Cliente
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-8">
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
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold">{cliente.nombre}</h3>
                        {getPropietarioBadge(cliente.propietario)}
                        {cliente.estado === 'pendiente_validacion' && (
                          <Badge className="bg-yellow-100 text-yellow-800">Pendiente Validación</Badge>
                        )}
                        {cliente.estado === 'activo' && (
                          <Badge className="bg-green-100 text-green-800">Activo</Badge>
                        )}
                        {!cliente.activo && (
                          <Badge variant="secondary">Inactivo</Badge>
                        )}
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-slate-600">
                        {cliente.telefono_completo && (
                          <div className="flex items-center gap-2">
                            <span className="font-medium">📱</span>
                            <span>{cliente.telefono_completo}</span>
                          </div>
                        )}
                        {cliente.email && (
                          <div className="flex items-center gap-2">
                            <span className="font-medium">📧</span>
                            <span>{cliente.email}</span>
                          </div>
                        )}
                        {cliente.rfc && (
                          <div className="flex items-center gap-2">
                            <span className="font-medium">🆔</span>
                            <span>{cliente.rfc}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          <span className="font-medium">📅</span>
                          <span>Alta: {formatFecha(cliente.fecha_alta)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">💰</span>
                          <span>Comisión: {cliente.porcentaje_comision_cliente}%</span>
                        </div>
                        {cliente.telegram_id && (
                          <div className="flex items-center gap-2">
                            <span className="font-medium">✈️</span>
                            <span>Telegram conectado</span>
                          </div>
                        )}
                      </div>

                      {cliente.notas && (
                        <div className="mt-3 p-3 bg-slate-50 rounded-lg text-sm text-slate-600">
                          <span className="font-medium">Notas:</span> {cliente.notas}
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {showNuevoCliente && (
        <NuevoClienteModal
          onClose={() => setShowNuevoCliente(false)}
          onSuccess={cargarClientes}
        />
      )}
    </div>
  );
};

export default Clientes;
