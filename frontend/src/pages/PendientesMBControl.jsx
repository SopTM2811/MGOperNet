import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Home as HomeIcon, Save, AlertCircle, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PendientesMBControl = () => {
  const navigate = useNavigate();
  const [operaciones, setOperaciones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState({});
  const [clavesMBControl, setClavesMBControl] = useState({});

  useEffect(() => {
    cargarOperacionesPendientes();
  }, []);

  const cargarOperacionesPendientes = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/operaciones`);
      
      // Filtrar operaciones que tienen datos completos pero no tienen clave MBControl
      // Incluye DATOS_COMPLETOS (nuevo) y ESPERANDO_CODIGO_SISTEMA (legacy)
      const estadosValidos = ['DATOS_COMPLETOS', 'ESPERANDO_CODIGO_SISTEMA'];
      const pendientes = response.data.filter(op => 
        estadosValidos.includes(op.estado) && 
        !op.clave_operacion_mbcontrol
      );
      
      setOperaciones(pendientes);
    } catch (error) {
      console.error('Error cargando operaciones:', error);
      toast.error('Error al cargar operaciones pendientes');
    } finally {
      setLoading(false);
    }
  };

  const handleGuardarClave = async (operacionId) => {
    const clave = clavesMBControl[operacionId]?.trim();
    
    if (!clave) {
      toast.error('Por favor ingresa una clave MBControl');
      return;
    }
    
    try {
      setGuardando(prev => ({ ...prev, [operacionId]: true }));
      
      const formData = new FormData();
      formData.append('clave_mbcontrol', clave);
      
      const response = await axios.post(
        `${API}/operaciones/${operacionId}/mbcontrol`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      );
      
      if (response.data.success) {
        toast.success(response.data.mensaje || 'Clave MBControl registrada y layout generado');
        // Recargar operaciones pendientes
        cargarOperacionesPendientes();
        // Limpiar el campo
        setClavesMBControl(prev => {
          const nuevas = { ...prev };
          delete nuevas[operacionId];
          return nuevas;
        });
      }
    } catch (error) {
      console.error('Error guardando clave:', error);
      toast.error(error.response?.data?.detail || 'Error al guardar clave MBControl');
    } finally {
      setGuardando(prev => ({ ...prev, [operacionId]: false }));
    }
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
    <div className="min-h-screen bg-white py-4 sm:py-8">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header - Mismo diseño que Dashboard */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 sm:mb-12">
          <div>
            <h1 
              className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-1 sm:mb-2 tracking-tight"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Pendientes MBControl
            </h1>
            <p className="text-sm sm:text-base text-slate-600 font-light">Operaciones que necesitan clave de operación</p>
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
              <ArrowLeft className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Dashboard</span>
            </Button>
          </div>
        </div>

        {/* Stats */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="text-sm text-slate-600">Operaciones pendientes</div>
                <div className="text-3xl font-bold">{operaciones.length}</div>
              </div>
              {operaciones.length > 0 && (
                <div className="px-4 py-2 bg-amber-50 border-l-4 border-amber-400 rounded-r text-sm text-amber-800">
                  <AlertCircle className="h-4 w-4 inline mr-2" />
                  Requieren atención
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Lista de operaciones */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-600">Cargando operaciones...</p>
          </div>
        ) : operaciones.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <AlertCircle className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600 text-lg mb-2">
                ✅ No hay operaciones pendientes
              </p>
              <p className="text-sm text-slate-500">
                Todas las operaciones tienen su clave MBControl asignada
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {operaciones.map((operacion) => {
              const comprobantesValidos = operacion.comprobantes?.filter(c => c.es_valido) || [];
              const montoTotal = operacion.monto_total_comprobantes || 
                comprobantesValidos.reduce((sum, c) => sum + (c.monto || 0), 0);
              const comisionCobrada = operacion.comision_cobrada || 0;
              const capitalNetcash = operacion.capital_netcash || (montoTotal - comisionCobrada);

              return (
                <Card key={operacion.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {operacion.folio_mbco && (
                            <Badge className="bg-blue-600 text-white font-semibold">
                              {operacion.folio_mbco}
                            </Badge>
                          )}
                          <span className="text-lg">{operacion.cliente_nombre || 'Cliente desconocido'}</span>
                        </CardTitle>
                        <CardDescription className="mt-1">
                          Creada: {formatFecha(operacion.fecha_creacion)}
                        </CardDescription>
                      </div>
                      <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
                        ✓ Datos Completos
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-2 gap-6">
                      {/* Información de la operación */}
                      <div className="space-y-3">
                        <h4 className="font-semibold text-slate-700">Detalles de la operación</h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-slate-600">Total comprobantes:</span>
                            <span className="font-semibold">${montoTotal.toLocaleString('es-MX', {minimumFractionDigits: 2})}</span>
                          </div>
                          {comisionCobrada > 0 && (
                            <>
                              <div className="flex justify-between">
                                <span className="text-slate-600">Comisión cobrada:</span>
                                <span className="font-semibold">${comisionCobrada.toLocaleString('es-MX', {minimumFractionDigits: 2})}</span>
                              </div>
                              <div className="flex justify-between border-t pt-2">
                                <span className="text-slate-600 font-semibold">Capital NetCash:</span>
                                <span className="font-bold text-green-700">${capitalNetcash.toLocaleString('es-MX', {minimumFractionDigits: 2})}</span>
                              </div>
                            </>
                          )}
                          <div className="flex justify-between">
                            <span className="text-slate-600">Titular:</span>
                            <span className="font-semibold">{operacion.titular_nombre_completo || operacion.nombre_ligas || '-'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-600">Cantidad de ligas:</span>
                            <span className="font-semibold">{operacion.numero_ligas || operacion.cantidad_ligas || '-'}</span>
                          </div>
                        </div>
                      </div>

                      {/* Captura de clave MBControl */}
                      <div className="space-y-3">
                        <h4 className="font-semibold text-slate-700">Clave de operación MBControl</h4>
                        <div className="space-y-3">
                          <div>
                            <Label htmlFor={`clave-${operacion.id}`}>
                              Clave operación MBControl *
                            </Label>
                            <Input
                              id={`clave-${operacion.id}`}
                              placeholder="Ej: 18434-138-D-11"
                              value={clavesMBControl[operacion.id] || ''}
                              onChange={(e) => setClavesMBControl(prev => ({
                                ...prev,
                                [operacion.id]: e.target.value
                              }))}
                              disabled={guardando[operacion.id]}
                            />
                            <p className="text-xs text-slate-500 mt-1">
                              Esta clave se usará para generar el layout SPEI
                            </p>
                          </div>
                          <Button
                            onClick={() => handleGuardarClave(operacion.id)}
                            disabled={guardando[operacion.id] || !clavesMBControl[operacion.id]?.trim()}
                            className="w-full"
                          >
                            {guardando[operacion.id] ? (
                              <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                                Procesando...
                              </>
                            ) : (
                              <>
                                <Save className="h-4 w-4 mr-2" />
                                Guardar y generar layout
                              </>
                            )}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PendientesMBControl;
