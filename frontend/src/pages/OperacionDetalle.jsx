import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, User, Calculator, Check, FileText, Clock, Mail, Phone, MessageCircle, Lock, Trash2, Home as HomeIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import ComprobantesUpload from '@/components/ComprobantesUpload';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const OperacionDetalle = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [operacion, setOperacion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showDeleteComprobante, setShowDeleteComprobante] = useState(false);
  const [comprobanteToDelete, setComprobanteToDelete] = useState(null);
  
  // Formulario titular
  const [titular, setTitular] = useState({
    nombre: '',
    idmex: '',
    numLigas: 1
  });

  useEffect(() => {
    cargarOperacion();
  }, [id]);

  const cargarOperacion = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/operaciones/${id}`);
      setOperacion(response.data);
    } catch (error) {
      console.error('Error cargando operación:', error);
      toast.error('Error al cargar operación');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file);

      await axios.post(`${API}/operaciones/${id}/comprobante`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      toast.success('Comprobante procesado exitosamente');
      cargarOperacion();
    } catch (error) {
      console.error('Error subiendo comprobante:', error);
      toast.error('Error al procesar comprobante');
    } finally {
      setUploading(false);
    }
  };

  const handleGuardarTitular = async (e) => {
    e.preventDefault();
    
    try {
      const formData = new FormData();
      formData.append('titular_nombre_completo', titular.nombre);
      formData.append('titular_idmex', titular.idmex);
      formData.append('numero_ligas', titular.numLigas);

      await axios.post(`${API}/operaciones/${id}/titular`, formData);
      
      toast.success('Datos del titular guardados');
      cargarOperacion();
    } catch (error) {
      console.error('Error guardando titular:', error);
      toast.error(error.response?.data?.detail || 'Error al guardar datos');
    }
  };

  const handleCalcular = async (comisionPorcentaje = null) => {
    try {
      const params = comisionPorcentaje ? { comision_cliente_porcentaje: comisionPorcentaje } : {};
      await axios.post(`${API}/operaciones/${id}/calcular`, null, { params });
      
      toast.success('Cálculos realizados');
      cargarOperacion();
    } catch (error) {
      console.error('Error calculando:', error);
      toast.error('Error al calcular');
    }
  };

  const handleConfirmar = async () => {
    try {
      await axios.post(`${API}/operaciones/${id}/confirmar`);
      
      toast.success('Operación confirmada');
      cargarOperacion();
    } catch (error) {
      console.error('Error confirmando:', error);
      toast.error('Error al confirmar operación');
    }
  };

  const handleDeleteComprobanteClick = (idx, comp) => {
    setComprobanteToDelete({ idx, comp });
    setShowDeleteComprobante(true);
  };

  const handleConfirmDeleteComprobante = async () => {
    if (comprobanteToDelete === null) return;
    
    try {
      await axios.delete(`${API}/operaciones/${id}/comprobantes/${comprobanteToDelete.idx}`);
      toast.success('Comprobante eliminado correctamente');
      setShowDeleteComprobante(false);
      setComprobanteToDelete(null);
      cargarOperacion();
    } catch (error) {
      console.error('Error eliminando comprobante:', error);
      toast.error('Error al eliminar el comprobante');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center">
        <div className="animate-pulse text-slate-400">Cargando operación...</div>
      </div>
    );
  }

  if (!operacion) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">Operación no encontrada</p>
          <Button onClick={() => navigate('/dashboard')}>Volver al Dashboard</Button>
        </div>
      </div>
    );
  }

  const comprobantesValidos = operacion.comprobantes.filter(c => c.es_valido);
  
  // MODO ESPEJO: Deshabilitar edición para operaciones de Telegram en estados cerrados
  const esOrigenTelegram = operacion.origen_operacion === 'telegram';
  const estadosCerrados = [
    'COMPROBANTES_CERRADOS',
    'DATOS_COMPLETOS',
    'ESPERANDO_CODIGO_SISTEMA',
    'PENDIENTE_ENVIO_LAYOUT',
    'LAYOUT_ENVIADO',
    'PENDIENTE_PAGO_PROVEEDOR',
    'ESPERANDO_TESORERIA',
    'COMPLETADO'
  ];
  const esSoloLectura = esOrigenTelegram && estadosCerrados.includes(operacion.estado);
  
  // Compatibilidad: soporte para nombres de campo antiguos y nuevos
  const montoTotalComprobantes = operacion.monto_depositado_cliente || operacion.monto_total_comprobantes || 0;
  const utilidadNeta = operacion.capital_netcash || operacion.utilidad_neta || 0;
  const tieneCalculos = (montoTotalComprobantes > 0 && operacion.comision_cobrada);
  
  const puedeAgregarTitular = !esSoloLectura && comprobantesValidos.length > 0 && !operacion.titular_nombre_completo;
  const puedeCalcular = !esSoloLectura && operacion.titular_nombre_completo && !tieneCalculos;
  const puedeConfirmar = !esSoloLectura && tieneCalculos && operacion.estado === 'ESPERANDO_CONFIRMACION_CLIENTE';

  return (
    <div className="min-h-screen bg-white py-4 sm:py-8">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-6xl">
        {/* Header - Mismo diseño que Dashboard */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 sm:mb-12">
          <div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-1 sm:mb-2">
              <h1 
                className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight"
                style={{ fontFamily: 'Space Grotesk, sans-serif' }}
                data-testid="operation-title"
              >
                Operación NetCash
              </h1>
              {/* Badge de origen */}
              {operacion.origen === 'telegram' && (
                <Badge variant="outline" className="border-blue-400 text-blue-600 text-xs">
                  📱 Telegram
                </Badge>
              )}
              {operacion.modo_captura === 'manual_por_fallo_ocr' && (
                <Badge variant="outline" className="border-amber-400 text-amber-600 text-xs">
                  ✋ Manual
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              {operacion.folio_mbco && (
                <Badge className="bg-blue-600 text-white font-semibold text-sm sm:text-lg px-3 sm:px-4 py-1">
                  {operacion.folio_mbco}
                </Badge>
              )}
              <code className="text-xs sm:text-sm font-mono bg-slate-100 px-2 sm:px-3 py-1 rounded text-slate-500">{operacion.id}</code>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 sm:gap-3">
            <Button
              variant="outline"
              onClick={() => navigate('/')}
              className="border-slate-300 text-sm"
              size="sm"
              data-testid="home-btn"
            >
              <HomeIcon className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Inicio</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/dashboard')}
              className="border-slate-300 text-sm"
              size="sm"
              data-testid="back-btn"
            >
              <ArrowLeft className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Dashboard</span>
            </Button>
          </div>
        </div>
            </div>
            <Badge variant="default" className="text-base px-4 py-2">
              {operacion.estado.replace(/_/g, ' ')}
            </Badge>
          </div>
        </div>

        {/* Mensaje informativo para modo espejo */}
        {esSoloLectura && (
          <div className="mb-6 bg-blue-50 border-l-4 border-blue-600 p-4 rounded-lg">
            <div className="flex items-start gap-3">
              <MessageCircle className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <p className="font-semibold text-blue-900 mb-1">
                  🔒 Operación creada desde Telegram (Solo lectura)
                </p>
                <p className="text-sm text-blue-800">
                  Los datos de esta operación fueron capturados por el cliente en Telegram y ya están confirmados. 
                  No se permite modificar la información desde el panel web para mantener la integridad de los datos.
                </p>
              </div>
            </div>
          </div>
        )}

        <Tabs defaultValue="general" className="space-y-6">
          <TabsList>
            <TabsTrigger value="general" data-testid="tab-general">General</TabsTrigger>
            <TabsTrigger value="comprobantes" data-testid="tab-comprobantes">Comprobantes</TabsTrigger>
            <TabsTrigger value="titular" data-testid="tab-titular">Titular</TabsTrigger>
            <TabsTrigger value="calculos" data-testid="tab-calculos">Cálculos</TabsTrigger>
          </TabsList>

          {/* Tab General */}
          <TabsContent value="general">
            <div className="space-y-6">
              {/* Origen de la operación */}
              {esOrigenTelegram && (
                <Card className="border-blue-200 bg-blue-50">
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-3">
                      <MessageCircle className="h-6 w-6 text-blue-600" />
                      <div>
                        <p className="font-semibold text-blue-900">Origen: Telegram</p>
                        <p className="text-sm text-blue-700">
                          Esta operación fue creada y gestionada por el cliente a través del bot de Telegram
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Información del Cliente */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Información del Cliente
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label className="text-slate-600 text-sm">Nombre del Cliente</Label>
                      <p className="font-semibold text-lg">{operacion.cliente_nombre || '-'}</p>
                    </div>
                    
                    <div>
                      <Label className="text-slate-600 text-sm">Propietario</Label>
                      <p className="font-medium">{operacion.propietario || '-'}</p>
                    </div>
                    
                    {operacion.cliente_email && (
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4 text-blue-600" />
                        <div>
                          <Label className="text-slate-600 text-sm">Email</Label>
                          <p className="font-medium">{operacion.cliente_email}</p>
                        </div>
                      </div>
                    )}
                    
                    {operacion.cliente_telefono_completo && (
                      <div className="flex items-center gap-2">
                        <Phone className="h-4 w-4 text-blue-600" />
                        <div>
                          <Label className="text-slate-600 text-sm">Teléfono / WhatsApp</Label>
                          <p className="font-medium">{operacion.cliente_telefono_completo}</p>
                        </div>
                      </div>
                    )}
                    
                    {operacion.cliente_telegram_id && (
                      <div className="flex items-center gap-2">
                        <MessageCircle className="h-4 w-4 text-blue-600" />
                        <div>
                          <Label className="text-slate-600 text-sm">Telegram</Label>
                          <p className="font-medium">{operacion.cliente_telegram_id}</p>
                        </div>
                      </div>
                    )}
                    
                    {operacion.porcentaje_comision_usado !== null && (
                      <div className="bg-blue-50 rounded-lg p-3">
                        <Label className="text-slate-600 text-sm">Comisión de esta operación</Label>
                        <p className="font-semibold text-blue-700 text-lg">{operacion.porcentaje_comision_usado}%</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Información de la Operación */}
              <Card>
                <CardHeader>
                  <CardTitle>Detalles de la Operación</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label className="text-slate-600 text-sm">Fecha de creación</Label>
                      <p className="font-medium">
                        {new Date(operacion.fecha_creacion).toLocaleString('es-MX')}
                      </p>
                    </div>
                    <div>
                      <Label className="text-slate-600 text-sm">Código del Sistema</Label>
                      <p className="font-medium">{operacion.codigo_operacion_sistema || 'Pendiente'}</p>
                    </div>
                    
                    {/* Clave MBco / MBControl */}
                    <div className="md:col-span-2">
                      <Label className="text-slate-600 text-sm">Clave MBco / MBControl</Label>
                      {operacion.clave_operacion_mbcontrol ? (
                        <div className="flex items-center gap-2 mt-1">
                          <Badge className="bg-green-600 text-white font-mono text-base px-4 py-1.5">
                            {operacion.clave_operacion_mbcontrol}
                          </Badge>
                          {operacion.timestamp_mbcontrol && (
                            <span className="text-xs text-slate-500">
                              Registrada: {new Date(operacion.timestamp_mbcontrol).toLocaleString('es-MX')}
                            </span>
                          )}
                        </div>
                      ) : (
                        <p className="font-medium text-slate-400 italic mt-1">Sin clave registrada</p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Tab Comprobantes */}
          <TabsContent value="comprobantes">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Comprobantes de Depósito
                </CardTitle>
                <CardDescription>
                  {esSoloLectura 
                    ? "Comprobantes procesados por el cliente en Telegram"
                    : "Sube y procesa comprobantes de depósito con validación automática"
                  }
                </CardDescription>
              </CardHeader>
              <CardContent>
                {esSoloLectura && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                    <p className="text-sm text-amber-800">
                      ℹ️ Los comprobantes fueron subidos por el cliente en Telegram. No se permite agregar más desde el panel web.
                    </p>
                  </div>
                )}
                
                {/* Mostrar comprobantes existentes */}
                {operacion.comprobantes && operacion.comprobantes.length > 0 ? (
                  <div className="space-y-3">
                    {operacion.comprobantes.map((comp, idx) => (
                      <div 
                        key={idx}
                        className={`border rounded-lg p-4 ${comp.es_valido ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
                      >
                        <div className="flex justify-between items-start gap-4">
                          <div className="flex-1">
                            <p className="font-medium mb-2">
                              {comp.es_valido ? '✅' : '❌'} Comprobante {idx + 1}
                              {comp.nombre_archivo && (
                                <span className="text-xs text-slate-500 ml-2">({comp.nombre_archivo})</span>
                              )}
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-slate-600">
                              <div>
                                <span className="font-medium">Monto:</span> ${comp.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2}) || '0.00'}
                              </div>
                              {comp.banco_origen && (
                                <div>
                                  <span className="font-medium">Banco del cliente:</span> {comp.banco_origen}
                                </div>
                              )}
                              {comp.clave_rastreo && (
                                <div>
                                  <span className="font-medium">Clave rastreo:</span> {comp.clave_rastreo}
                                </div>
                              )}
                              {comp.cuenta_origen && (
                                <div>
                                  <span className="font-medium">Cuenta origen:</span> {comp.cuenta_origen}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2 mt-3">
                              {comp.file_url && (
                                <Button
                                  size="sm"
                                  className="bg-blue-600 hover:bg-blue-700 text-white shadow-md"
                                  onClick={() => window.open(comp.file_url, '_blank')}
                                >
                                  <FileText className="h-4 w-4 mr-2" />
                                  Ver comprobante
                                </Button>
                              )}
                              {!esSoloLectura && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                                  onClick={() => handleDeleteComprobanteClick(idx, comp)}
                                >
                                  <Trash2 className="h-4 w-4 mr-2" />
                                  Eliminar
                                </Button>
                              )}
                            </div>
                          </div>
                          <Badge variant={comp.es_valido ? 'success' : 'destructive'}>
                            {comp.es_valido ? 'Válido' : 'Inválido'}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 text-sm">No hay comprobantes registrados</p>
                )}
                
                {/* Solo mostrar componente de subida si NO es solo lectura */}
                {!esSoloLectura && (
                  <div className="mt-4">
                    <ComprobantesUpload
                      operacionId={operacion.id}
                      comprobantes={operacion.comprobantes || []}
                      onComprobantesActualizados={cargarOperacion}
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab Titular */}
          <TabsContent value="titular">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5" />
                  Datos del Titular
                </CardTitle>
                <CardDescription>
                  Información del titular de las ligas NetCash
                </CardDescription>
              </CardHeader>
              <CardContent>
                {operacion.titular_nombre_completo || operacion.nombre_ligas ? (
                  <div className="space-y-4">
                    <div>
                      <Label className="text-slate-600">Nombre completo</Label>
                      <p className="font-medium text-lg">
                        {operacion.titular_nombre_completo || operacion.nombre_ligas}
                      </p>
                    </div>
                    <div>
                      <Label className="text-slate-600">IDMEX (INE)</Label>
                      <p className="font-medium">{operacion.titular_idmex || '-'}</p>
                    </div>
                    <div>
                      <Label className="text-slate-600">Cantidad de ligas</Label>
                      <p className="font-medium">
                        {operacion.numero_ligas || operacion.cantidad_ligas || '-'}
                      </p>
                    </div>
                    {esSoloLectura && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mt-4">
                        <p className="text-sm text-blue-800">
                          ℹ️ Datos capturados por el cliente en Telegram
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <form onSubmit={handleGuardarTitular} className="space-y-4">
                    {!puedeAgregarTitular && (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                        <p className="text-sm text-amber-800">
                          Primero debes subir y validar al menos un comprobante válido.
                        </p>
                      </div>
                    )}
                    
                    <div>
                      <Label htmlFor="nombre">Nombre completo del titular *</Label>
                      <Input
                        id="nombre"
                        placeholder="Nombre y dos apellidos"
                        value={titular.nombre}
                        onChange={(e) => setTitular({...titular, nombre: e.target.value})}
                        disabled={!puedeAgregarTitular}
                        required
                        data-testid="titular-nombre-input"
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        Mínimo 3 palabras (nombre + 2 apellidos)
                      </p>
                    </div>

                    <div>
                      <Label htmlFor="idmex">IDMEX de la INE *</Label>
                      <Input
                        id="idmex"
                        placeholder="IDMEX"
                        value={titular.idmex}
                        onChange={(e) => setTitular({...titular, idmex: e.target.value})}
                        disabled={!puedeAgregarTitular}
                        required
                        data-testid="titular-idmex-input"
                      />
                    </div>

                    <div>
                      <Label htmlFor="numLigas">Número de ligas *</Label>
                      <Input
                        id="numLigas"
                        type="number"
                        min="1"
                        value={titular.numLigas}
                        onChange={(e) => setTitular({...titular, numLigas: parseInt(e.target.value)})}
                        disabled={!puedeAgregarTitular}
                        required
                        data-testid="titular-ligas-input"
                      />
                    </div>

                    <Button
                      type="submit"
                      disabled={!puedeAgregarTitular}
                      data-testid="save-titular-btn"
                      className={!puedeAgregarTitular ? 'bg-slate-300 text-slate-500' : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md'}
                    >
                      <Check className="h-4 w-4 mr-2" />
                      Guardar Datos del Titular
                    </Button>
                  </form>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab Cálculos */}
          <TabsContent value="calculos">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calculator className="h-5 w-5" />
                  Cálculos Financieros NetCash
                </CardTitle>
                <CardDescription>
                  Montos, comisiones y utilidades de la operación
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {tieneCalculos ? (
                  <div className="space-y-6">
                    {/* Sección 1: Totales de operación */}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-700 mb-3">1️⃣ Totales de operación</h3>
                      <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                        <Label className="text-slate-600 text-sm">Monto total de comprobantes</Label>
                        <p className="text-3xl font-bold text-blue-700">
                          ${montoTotalComprobantes.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                      </div>
                    </div>

                    {/* Sección 2: Comisión al cliente */}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-700 mb-3">2️⃣ Comisión al cliente</h3>
                      <div className="grid md:grid-cols-2 gap-4">
                        <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
                          <Label className="text-slate-600 text-sm">Porcentaje comisión cliente</Label>
                          <p className="text-2xl font-bold text-amber-700">
                            {operacion.porcentaje_comision_usado || 1.0}%
                          </p>
                        </div>
                        <div className="bg-amber-100 rounded-lg p-4 border border-amber-300">
                          <Label className="text-slate-600 text-sm">Importe comisión cliente</Label>
                          <p className="text-2xl font-bold text-amber-800">
                            ${operacion.comision_cobrada.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            ${montoTotalComprobantes.toLocaleString('es-MX')} × {operacion.porcentaje_comision_usado || 1.0}%
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Sección 3: Costo proveedor DNS (solo interno) */}
                    <div className="p-4 bg-slate-50 border-l-4 border-slate-600 rounded">
                      <div className="flex items-center gap-2 mb-3">
                        <Lock className="h-4 w-4 text-slate-700" />
                        <h3 className="text-sm font-semibold text-slate-700">3️⃣ Costo proveedor DNS (solo interno)</h3>
                      </div>
                      <div className="grid md:grid-cols-2 gap-4">
                        <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
                          <Label className="text-slate-600 text-sm">Porcentaje costo proveedor</Label>
                          <p className="text-2xl font-bold text-orange-700">
                            {operacion.costo_proveedor_pct ? (operacion.costo_proveedor_pct * 100).toFixed(3) : '0.375'}%
                          </p>
                          <p className="text-xs text-slate-500 mt-1">Fijo para proveedor DNS</p>
                        </div>
                        <div className="bg-orange-100 rounded-lg p-4 border border-orange-300">
                          <Label className="text-slate-600 text-sm">Importe costo proveedor</Label>
                          <p className="text-2xl font-bold text-orange-800">
                            ${(operacion.costo_proveedor_monto || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            ${montoTotalComprobantes.toLocaleString('es-MX')} × 0.375%
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Sección 4: Resultado - Capital NetCash */}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-700 mb-3">4️⃣ Resultado</h3>
                      <div className="bg-green-50 rounded-lg p-4 border-2 border-green-400">
                        <Label className="text-slate-600 text-sm">Capital NetCash (a dispersar)</Label>
                        <p className="text-4xl font-bold text-green-700">
                          ${utilidadNeta.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                        <p className="text-sm text-slate-600 mt-2">
                          Monto depositado (${montoTotalComprobantes.toLocaleString('es-MX', {minimumFractionDigits: 2})}) 
                          - Comisión cliente (${(operacion.comision_cobrada || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})})
                        </p>
                      </div>
                    </div>

                    {/* Nota importante */}
                    <div className="mt-4 text-xs text-slate-600 bg-yellow-50 p-3 rounded border border-yellow-200">
                      <p className="font-semibold mb-1">⚠️ INFORMACIÓN CONFIDENCIAL</p>
                      <p>Los datos de costo proveedor DNS NO deben mostrarse al cliente en ningún reporte, PDF o comunicación externa.</p>
                    </div>

                    {puedeConfirmar && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4 mt-6">
                        <p className="text-sm text-green-800 mb-3">
                          ¿Los cálculos son correctos? Al confirmar, la operación se enviará a Ana para generar el código del sistema.
                        </p>
                        <Button
                          onClick={handleConfirmar}
                          className="bg-green-600 hover:bg-green-700"
                          data-testid="confirm-operation-btn"
                        >
                          <Check className="h-4 w-4 mr-2" />
                          Confirmar Operación
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    {!puedeCalcular ? (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                        <Clock className="h-12 w-12 mx-auto mb-4 text-amber-500" />
                        <p className="text-amber-800 font-semibold">
                          Completa los pasos anteriores para calcular los montos
                        </p>
                        <p className="text-sm text-amber-600 mt-2">
                          Necesitas: comprobantes válidos y datos del titular
                        </p>
                      </div>
                    ) : (
                      <div>
                        <Calculator className="h-12 w-12 mx-auto mb-4 text-blue-500" />
                        <p className="text-slate-600 mb-4">
                          Listo para calcular los montos de la operación
                        </p>
                        <Button
                          onClick={() => handleCalcular()}
                          className="bg-blue-600 hover:bg-blue-700"
                          data-testid="calculate-btn"
                        >
                          <Calculator className="h-4 w-4 mr-2" />
                          Calcular Montos
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Diálogo de confirmación para eliminar comprobante */}
      <AlertDialog open={showDeleteComprobante} onOpenChange={setShowDeleteComprobante}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este comprobante?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. Se eliminará permanentemente el comprobante 
              {comprobanteToDelete && (
                <span className="font-semibold"> #{comprobanteToDelete.idx + 1}</span>
              )}
              {comprobanteToDelete?.comp?.monto && (
                <span> con monto de <span className="font-semibold">
                  ${comprobanteToDelete.comp.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                </span></span>
              )}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="hover:bg-slate-100">Cancelar</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleConfirmDeleteComprobante}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              Sí, eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default OperacionDetalle;