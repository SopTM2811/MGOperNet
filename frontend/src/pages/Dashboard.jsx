import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Plus, Search, Filter, FileText, Clock, CheckCircle, AlertCircle, Home as HomeIcon, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import NuevaOperacionModal from '@/components/NuevaOperacionModal';
import ComprobantesModal from '@/components/ComprobantesModal';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Dashboard = () => {
  const navigate = useNavigate();
  const [operaciones, setOperaciones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showNuevaOperacion, setShowNuevaOperacion] = useState(false);
  const [showComprobantes, setShowComprobantes] = useState(false);
  const [operacionSeleccionada, setOperacionSeleccionada] = useState(null);
  const [stats, setStats] = useState({
    total: 0,
    completadas: 0,
    en_proceso: 0,
    pendientes: 0
  });

  useEffect(() => {
    cargarOperaciones();
  }, []);

  const cargarOperaciones = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/operaciones`);
      setOperaciones(response.data);
      calcularStats(response.data);
    } catch (error) {
      console.error('Error cargando operaciones:', error);
      toast.error('Error al cargar operaciones');
    } finally {
      setLoading(false);
    }
  };

  const calcularStats = (ops) => {
    const total = ops.length;
    const completadas = ops.filter(op => op.estado === 'COMPLETADO').length;
    const en_proceso = ops.filter(op => 
      ['VALIDANDO_COMPROBANTES', 'ESPERANDO_DATOS_TITULAR', 'ESPERANDO_CONFIRMACION_CLIENTE',
       'ESPERANDO_CODIGO_SISTEMA', 'PENDIENTE_PAGO_PROVEEDOR', 'ESPERANDO_TESORERIA',
       'ESPERANDO_PROVEEDOR', 'LISTO_PARA_ENTREGAR'].includes(op.estado)
    ).length;
    const pendientes = ops.filter(op => op.estado === 'ESPERANDO_COMPROBANTES').length;

    setStats({ total, completadas, en_proceso, pendientes });
  };

  const operacionesFiltradas = operaciones.filter(op => 
    op.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (op.cliente_nombre && op.cliente_nombre.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (op.codigo_operacion_sistema && op.codigo_operacion_sistema.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const getEstadoBadge = (estado) => {
    const estadoMap = {
      'ESPERANDO_COMPROBANTES': { variant: 'secondary', label: 'Esperando Comprobantes', icon: Clock },
      'VALIDANDO_COMPROBANTES': { variant: 'default', label: 'Validando', icon: Search },
      'ESPERANDO_DATOS_TITULAR': { variant: 'default', label: 'Esperando Datos', icon: AlertCircle },
      'ESPERANDO_CONFIRMACION_CLIENTE': { variant: 'warning', label: 'Por Confirmar', icon: AlertCircle },
      'ESPERANDO_CODIGO_SISTEMA': { variant: 'default', label: 'Generando Código', icon: Clock },
      'PENDIENTE_PAGO_PROVEEDOR': { variant: 'default', label: 'Pago Pendiente', icon: Clock },
      'ESPERANDO_TESORERIA': { variant: 'default', label: 'En Tesorería', icon: Clock },
      'ESPERANDO_PROVEEDOR': { variant: 'default', label: 'Con Proveedor', icon: Clock },
      'LISTO_PARA_ENTREGAR': { variant: 'success', label: 'Listo', icon: CheckCircle },
      'COMPLETADO': { variant: 'success', label: 'Completado', icon: CheckCircle }
    };

    const config = estadoMap[estado] || { variant: 'secondary', label: estado, icon: FileText };
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const formatFecha = (fecha) => {
    if (!fecha) return '-';
    const date = new Date(fecha);
    return date.toLocaleDateString('es-MX', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 py-8">
      <div className="container mx-auto px-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 
              className="text-4xl font-bold mb-2"
              style={{ fontFamily: 'Cormorant Garamond, serif' }}
              data-testid="dashboard-title"
            >
              Dashboard NetCash
            </h1>
            <p className="text-slate-600">Gestión de operaciones y monitoreo en tiempo real</p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => navigate('/')}
              data-testid="home-nav-btn"
            >
              <HomeIcon className="h-4 w-4 mr-2" />
              Inicio
            </Button>
            <Button
              onClick={() => setShowNuevaOperacion(true)}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="new-operation-btn"
            >
              <Plus className="h-4 w-4 mr-2" />
              Nueva Operación
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <StatsCard
            title="Total"
            value={stats.total}
            icon={<FileText className="h-6 w-6 text-blue-600" />}
            color="blue"
          />
          <StatsCard
            title="En Proceso"
            value={stats.en_proceso}
            icon={<Clock className="h-6 w-6 text-amber-600" />}
            color="amber"
          />
          <StatsCard
            title="Completadas"
            value={stats.completadas}
            icon={<CheckCircle className="h-6 w-6 text-emerald-600" />}
            color="emerald"
          />
          <StatsCard
            title="Pendientes"
            value={stats.pendientes}
            icon={<AlertCircle className="h-6 w-6 text-slate-600" />}
            color="slate"
          />
        </div>

        {/* Search and Filter */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <Input
                    placeholder="Buscar por ID, cliente o código de sistema..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                    data-testid="search-input"
                  />
                </div>
              </div>
              <Button variant="outline" data-testid="filter-btn">
                <Filter className="h-4 w-4 mr-2" />
                Filtros
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Operaciones Table */}
        <Card>
          <CardHeader>
            <CardTitle>Operaciones NetCash</CardTitle>
            <CardDescription>
              {operacionesFiltradas.length} operacion(es) encontrada(s)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-12">
                <div className="animate-pulse text-slate-400">Cargando operaciones...</div>
              </div>
            ) : operacionesFiltradas.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <FileText className="h-12 w-12 mx-auto mb-4 text-slate-300" />
                <p>No se encontraron operaciones</p>
              </div>
            ) : (
              <div className="space-y-3">
                {operacionesFiltradas.map((operacion) => (
                  <div
                    key={operacion.id}
                    className="border rounded-lg p-4 hover:bg-slate-50 transition-colors"
                    data-testid={`operation-card-${operacion.id}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div 
                        className="flex-1 cursor-pointer"
                        onClick={() => navigate(`/operacion/${operacion.id}`)}
                      >
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <code className="text-sm font-mono bg-slate-100 px-2 py-1 rounded">
                            {operacion.id.substring(0, 8)}...
                          </code>
                          {getEstadoBadge(operacion.estado)}
                          {operacion.codigo_operacion_sistema && (
                            <Badge variant="outline">
                              {operacion.codigo_operacion_sistema}
                            </Badge>
                          )}
                        </div>
                        <div className="text-sm text-slate-600">
                          <span className="font-medium">Cliente:</span> {operacion.cliente_nombre || 'Sin nombre'}
                          {' • '}
                          <span className="font-medium">Fecha:</span> {formatFecha(operacion.fecha_creacion)}
                        </div>
                        {operacion.calculos && (
                          <div className="text-sm text-slate-600 mt-1">
                            <span className="font-medium">Capital:</span> ${operacion.calculos.capital_netcash.toLocaleString('es-MX')}
                            {' • '}
                            <span className="font-medium">Depositado:</span> ${operacion.calculos.monto_depositado_cliente.toLocaleString('es-MX')}
                          </div>
                        )}
                      </div>
                      
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOperacionSeleccionada(operacion);
                          setShowComprobantes(true);
                        }}
                        className="shrink-0"
                        data-testid={`upload-btn-${operacion.id}`}
                      >
                        <Upload className="h-4 w-4 mr-2" />
                        Subir comprobantes
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Modal Nueva Operación */}
      {showNuevaOperacion && (
        <NuevaOperacionModal
          onClose={() => setShowNuevaOperacion(false)}
          onSuccess={() => {
            setShowNuevaOperacion(false);
            cargarOperaciones();
          }}
        />
      )}

      {/* Modal Subir Comprobantes */}
      {showComprobantes && operacionSeleccionada && (
        <ComprobantesModal
          operacion={operacionSeleccionada}
          onClose={() => {
            setShowComprobantes(false);
            setOperacionSeleccionada(null);
          }}
          onActualizado={() => {
            cargarOperaciones();
          }}
        />
      )}
    </div>
  );
};

const StatsCard = ({ title, value, icon, color }) => {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-600 mb-1">{title}</p>
            <p className="text-3xl font-bold">{value}</p>
          </div>
          <div className={`bg-${color}-100 rounded-full p-3`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default Dashboard;