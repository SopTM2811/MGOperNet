import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  Plus, Search, Home as HomeIcon, Users, Edit, Trash2, 
  ChevronDown, ChevronRight, RefreshCw 
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Beneficiarios = () => {
  const navigate = useNavigate();
  const [beneficiariosPorCliente, setBeneficiariosPorCliente] = useState({});
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedClientes, setExpandedClientes] = useState(new Set());
  
  // Modal states
  const [showNuevoBeneficiario, setShowNuevoBeneficiario] = useState(false);
  const [showEditarBeneficiario, setShowEditarBeneficiario] = useState(false);
  const [showEliminarConfirm, setShowEliminarConfirm] = useState(false);
  const [beneficiarioSeleccionado, setBeneficiarioSeleccionado] = useState(null);
  const [clienteParaNuevo, setClienteParaNuevo] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    nombre_beneficiario: '',
    idmex_beneficiario: '',
    cliente_id: ''
  });

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      setLoading(true);
      
      // Cargar clientes y beneficiarios en paralelo
      const [clientesRes, beneficiariosRes] = await Promise.all([
        axios.get(`${API}/clientes`),
        axios.get(`${API}/beneficiarios-frecuentes`)
      ]);
      
      setClientes(clientesRes.data);
      
      // Agrupar beneficiarios por cliente_id
      const agrupados = {};
      beneficiariosRes.data.forEach(ben => {
        const clienteId = ben.cliente_id;
        if (!agrupados[clienteId]) {
          agrupados[clienteId] = [];
        }
        agrupados[clienteId].push(ben);
      });
      
      setBeneficiariosPorCliente(agrupados);
      
    } catch (error) {
      console.error('Error cargando datos:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const toggleCliente = (clienteId) => {
    const newExpanded = new Set(expandedClientes);
    if (newExpanded.has(clienteId)) {
      newExpanded.delete(clienteId);
    } else {
      newExpanded.add(clienteId);
    }
    setExpandedClientes(newExpanded);
  };

  const getClienteNombre = (clienteId) => {
    const cliente = clientes.find(c => c.id === clienteId);
    return cliente?.nombre || clienteId;
  };

  // Filtrar clientes que tienen beneficiarios O que coinciden con la búsqueda
  const clientesFiltrados = clientes.filter(cliente => {
    const nombreMatch = cliente.nombre?.toLowerCase().includes(searchTerm.toLowerCase());
    const tieneBeneficiarios = beneficiariosPorCliente[cliente.id]?.length > 0;
    
    // Si hay búsqueda, también buscar en beneficiarios
    if (searchTerm) {
      const beneficiariosMatch = beneficiariosPorCliente[cliente.id]?.some(ben =>
        ben.nombre_beneficiario?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ben.idmex_beneficiario?.includes(searchTerm)
      );
      return nombreMatch || beneficiariosMatch;
    }
    
    return tieneBeneficiarios || nombreMatch;
  });

  const handleNuevoBeneficiario = (cliente = null) => {
    setClienteParaNuevo(cliente);
    setFormData({
      nombre_beneficiario: '',
      idmex_beneficiario: '',
      cliente_id: cliente?.id || ''
    });
    setShowNuevoBeneficiario(true);
  };

  const handleEditarBeneficiario = (beneficiario) => {
    setBeneficiarioSeleccionado(beneficiario);
    setFormData({
      nombre_beneficiario: beneficiario.nombre_beneficiario || '',
      idmex_beneficiario: beneficiario.idmex_beneficiario || '',
      cliente_id: beneficiario.cliente_id
    });
    setShowEditarBeneficiario(true);
  };

  const handleEliminarBeneficiario = (beneficiario) => {
    setBeneficiarioSeleccionado(beneficiario);
    setShowEliminarConfirm(true);
  };

  const guardarNuevoBeneficiario = async () => {
    if (!formData.nombre_beneficiario || !formData.idmex_beneficiario || !formData.cliente_id) {
      toast.error('Todos los campos son obligatorios');
      return;
    }

    // Validar IDMEX (10 dígitos)
    if (!/^\d{10}$/.test(formData.idmex_beneficiario)) {
      toast.error('El IDMEX debe tener exactamente 10 dígitos');
      return;
    }

    try {
      await axios.post(`${API}/beneficiarios-frecuentes`, {
        cliente_id: formData.cliente_id,
        nombre_beneficiario: formData.nombre_beneficiario.toUpperCase(),
        idmex_beneficiario: formData.idmex_beneficiario
      });
      
      toast.success('Beneficiario creado correctamente');
      setShowNuevoBeneficiario(false);
      cargarDatos();
    } catch (error) {
      console.error('Error creando beneficiario:', error);
      toast.error(error.response?.data?.detail || 'Error al crear beneficiario');
    }
  };

  const actualizarBeneficiario = async () => {
    if (!formData.nombre_beneficiario || !formData.idmex_beneficiario) {
      toast.error('Nombre e IDMEX son obligatorios');
      return;
    }

    if (!/^\d{10}$/.test(formData.idmex_beneficiario)) {
      toast.error('El IDMEX debe tener exactamente 10 dígitos');
      return;
    }

    try {
      await axios.put(`${API}/beneficiarios-frecuentes/${beneficiarioSeleccionado.id}`, {
        nombre_beneficiario: formData.nombre_beneficiario.toUpperCase(),
        idmex_beneficiario: formData.idmex_beneficiario
      });
      
      toast.success('Beneficiario actualizado');
      setShowEditarBeneficiario(false);
      cargarDatos();
    } catch (error) {
      console.error('Error actualizando beneficiario:', error);
      toast.error(error.response?.data?.detail || 'Error al actualizar');
    }
  };

  const eliminarBeneficiario = async () => {
    try {
      await axios.delete(`${API}/beneficiarios-frecuentes/${beneficiarioSeleccionado.id}`);
      toast.success('Beneficiario eliminado');
      setShowEliminarConfirm(false);
      setBeneficiarioSeleccionado(null);
      cargarDatos();
    } catch (error) {
      console.error('Error eliminando beneficiario:', error);
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    }
  };

  const totalBeneficiarios = Object.values(beneficiariosPorCliente).reduce(
    (acc, arr) => acc + arr.length, 0
  );

  return (
    <div className="min-h-screen bg-white py-4 sm:py-8">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 sm:mb-12">
          <div>
            <h1 
              className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-1 sm:mb-2 tracking-tight"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Beneficiarios
            </h1>
            <p className="text-sm sm:text-base text-slate-600 font-light">
              Gestión de beneficiarios frecuentes por cliente
            </p>
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
              onClick={() => navigate('/clientes')}
              className="border-slate-300 text-sm"
              size="sm"
            >
              <Users className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Clientes</span>
            </Button>
            <Button
              onClick={() => handleNuevoBeneficiario()}
              className="bg-black hover:bg-slate-800 text-white text-sm"
              size="sm"
            >
              <Plus className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Nuevo Beneficiario</span>
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Card className="border-slate-200">
            <CardContent className="pt-4 pb-4">
              <div className="text-2xl font-bold text-slate-900">{totalBeneficiarios}</div>
              <p className="text-sm text-slate-500">Beneficiarios totales</p>
            </CardContent>
          </Card>
          <Card className="border-slate-200">
            <CardContent className="pt-4 pb-4">
              <div className="text-2xl font-bold text-slate-900">
                {Object.keys(beneficiariosPorCliente).length}
              </div>
              <p className="text-sm text-slate-500">Clientes con beneficiarios</p>
            </CardContent>
          </Card>
        </div>

        {/* Search */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Buscar por cliente o beneficiario..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 border-slate-300"
            />
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={cargarDatos}
            className="border-slate-300"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        {/* Lista de clientes con beneficiarios */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-500">Cargando beneficiarios...</p>
          </div>
        ) : clientesFiltrados.length === 0 ? (
          <Card className="border-slate-200">
            <CardContent className="py-12 text-center">
              <Users className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">No hay beneficiarios registrados</p>
              <Button 
                className="mt-4 bg-black hover:bg-slate-800"
                onClick={() => handleNuevoBeneficiario()}
              >
                <Plus className="h-4 w-4 mr-2" />
                Agregar primer beneficiario
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {clientesFiltrados.map(cliente => {
              const beneficiarios = beneficiariosPorCliente[cliente.id] || [];
              const isExpanded = expandedClientes.has(cliente.id);
              
              return (
                <Card key={cliente.id} className="border-slate-200 overflow-hidden">
                  {/* Cliente Header */}
                  <div 
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50"
                    onClick={() => toggleCliente(cliente.id)}
                  >
                    <div className="flex items-center gap-3">
                      {isExpanded ? (
                        <ChevronDown className="h-5 w-5 text-slate-400" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-slate-400" />
                      )}
                      <div>
                        <h3 className="font-medium text-slate-900">{cliente.nombre}</h3>
                        <p className="text-sm text-slate-500">
                          {beneficiarios.length} beneficiario{beneficiarios.length !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNuevoBeneficiario(cliente);
                      }}
                      className="text-slate-600 hover:text-slate-900"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Beneficiarios List */}
                  {isExpanded && beneficiarios.length > 0 && (
                    <div className="border-t border-slate-100 bg-slate-50">
                      {beneficiarios.map((ben, idx) => (
                        <div 
                          key={ben.id}
                          className={`flex items-center justify-between px-4 py-3 ${
                            idx !== beneficiarios.length - 1 ? 'border-b border-slate-100' : ''
                          }`}
                        >
                          <div className="ml-8">
                            <p className="font-medium text-slate-800">{ben.nombre_beneficiario}</p>
                            <p className="text-sm text-slate-500">
                              IDMEX: {ben.idmex_beneficiario || '-'}
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditarBeneficiario(ben)}
                              className="text-slate-500 hover:text-blue-600"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEliminarBeneficiario(ben)}
                              className="text-slate-500 hover:text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {isExpanded && beneficiarios.length === 0 && (
                    <div className="border-t border-slate-100 bg-slate-50 p-4 text-center">
                      <p className="text-sm text-slate-500">Sin beneficiarios registrados</p>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal: Nuevo Beneficiario */}
      <Dialog open={showNuevoBeneficiario} onOpenChange={setShowNuevoBeneficiario}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nuevo Beneficiario</DialogTitle>
            <DialogDescription>
              {clienteParaNuevo 
                ? `Agregar beneficiario para ${clienteParaNuevo.nombre}`
                : 'Selecciona un cliente y registra el beneficiario'
              }
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {!clienteParaNuevo && (
              <div className="space-y-2">
                <Label>Cliente</Label>
                <Select 
                  value={formData.cliente_id} 
                  onValueChange={(value) => setFormData({...formData, cliente_id: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar cliente" />
                  </SelectTrigger>
                  <SelectContent>
                    {clientes.map(c => (
                      <SelectItem key={c.id} value={c.id}>{c.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label>Nombre del Beneficiario</Label>
              <Input
                placeholder="Nombre completo (mínimo 3 palabras)"
                value={formData.nombre_beneficiario}
                onChange={(e) => setFormData({...formData, nombre_beneficiario: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label>IDMEX</Label>
              <Input
                placeholder="10 dígitos"
                value={formData.idmex_beneficiario}
                onChange={(e) => setFormData({...formData, idmex_beneficiario: e.target.value.replace(/\D/g, '').slice(0, 10)})}
                maxLength={10}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNuevoBeneficiario(false)}>
              Cancelar
            </Button>
            <Button onClick={guardarNuevoBeneficiario} className="bg-black hover:bg-slate-800">
              Guardar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal: Editar Beneficiario */}
      <Dialog open={showEditarBeneficiario} onOpenChange={setShowEditarBeneficiario}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Editar Beneficiario</DialogTitle>
            <DialogDescription>
              Modifica los datos del beneficiario
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Nombre del Beneficiario</Label>
              <Input
                value={formData.nombre_beneficiario}
                onChange={(e) => setFormData({...formData, nombre_beneficiario: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label>IDMEX</Label>
              <Input
                value={formData.idmex_beneficiario}
                onChange={(e) => setFormData({...formData, idmex_beneficiario: e.target.value.replace(/\D/g, '').slice(0, 10)})}
                maxLength={10}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditarBeneficiario(false)}>
              Cancelar
            </Button>
            <Button onClick={actualizarBeneficiario} className="bg-black hover:bg-slate-800">
              Actualizar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal: Confirmar Eliminación */}
      <Dialog open={showEliminarConfirm} onOpenChange={setShowEliminarConfirm}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eliminar Beneficiario</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de eliminar a <strong>{beneficiarioSeleccionado?.nombre_beneficiario}</strong>? 
              Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEliminarConfirm(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={eliminarBeneficiario} 
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              Eliminar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Beneficiarios;
