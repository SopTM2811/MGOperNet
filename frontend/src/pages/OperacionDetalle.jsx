import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, User, Calculator, Check, FileText, Clock, Mail, Phone, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ComprobantesUpload from '@/components/ComprobantesUpload';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const OperacionDetalle = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [operacion, setOperacion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  
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
  
  const puedeAgregarTitular = !esSoloLectura && comprobantesValidos.length > 0 && !operacion.titular_nombre_completo;
  const puedeCalcular = !esSoloLectura && operacion.titular_nombre_completo && !operacion.calculos;
  const puedeConfirmar = !esSoloLectura && operacion.calculos && operacion.estado === 'ESPERANDO_CONFIRMACION_CLIENTE';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 py-8">
      <div className="container mx-auto px-6 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            onClick={() => navigate('/dashboard')}
            className="mb-4"
            data-testid="back-btn"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver al Dashboard
          </Button>
          
          <div className="flex justify-between items-start">
            <div>
              <h1 
                className="text-4xl font-bold mb-2"
                style={{ fontFamily: 'Cormorant Garamond, serif' }}
                data-testid="operation-title"
              >
                Operación NetCash
              </h1>
              <div className="flex items-center gap-3">
                {operacion.folio_mbco && (
                  <Badge className="bg-blue-600 text-white font-semibold text-lg px-4 py-1">
                    {operacion.folio_mbco}
                  </Badge>
                )}
                <code className="text-sm font-mono bg-white px-3 py-1 rounded border text-slate-500">{operacion.id}</code>
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
                  Sube y procesa comprobantes de depósito con validación automática
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ComprobantesUpload
                  operacionId={operacion.id}
                  comprobantes={operacion.comprobantes || []}
                  onComprobantesActualizados={cargarOperacion}
                />
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
                {operacion.titular_nombre_completo ? (
                  <div className="space-y-4">
                    <div>
                      <Label className="text-slate-600">Nombre completo</Label>
                      <p className="font-medium text-lg">{operacion.titular_nombre_completo}</p>
                    </div>
                    <div>
                      <Label className="text-slate-600">IDMEX (INE)</Label>
                      <p className="font-medium">{operacion.titular_idmex}</p>
                    </div>
                    <div>
                      <Label className="text-slate-600">Número de ligas</Label>
                      <p className="font-medium">{operacion.numero_ligas}</p>
                    </div>
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
                  Cálculos Financieros
                </CardTitle>
                <CardDescription>
                  Capital, comisiones y montos de la operación
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {operacion.calculos ? (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div className="bg-blue-50 rounded-lg p-4">
                        <Label className="text-slate-600 text-sm">Monto Depositado (Cliente)</Label>
                        <p className="text-2xl font-bold text-blue-700">
                          ${operacion.calculos.monto_depositado_cliente.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                      </div>

                      <div className="bg-emerald-50 rounded-lg p-4">
                        <Label className="text-slate-600 text-sm">Capital NetCash (Ligas)</Label>
                        <p className="text-2xl font-bold text-emerald-700">
                          ${operacion.calculos.capital_netcash.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                      </div>

                      <div className="bg-amber-50 rounded-lg p-4">
                        <Label className="text-slate-600 text-sm">Comisión Cliente ({(operacion.calculos.comision_cliente_porcentaje * 100).toFixed(2)}%)</Label>
                        <p className="text-2xl font-bold text-amber-700">
                          ${operacion.calculos.comision_cliente_cobrada.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                      </div>

                      <div className="bg-purple-50 rounded-lg p-4">
                        <Label className="text-slate-600 text-sm">Comisión Proveedor ({(operacion.calculos.comision_proveedor_porcentaje * 100).toFixed(3)}%)</Label>
                        <p className="text-2xl font-bold text-purple-700">
                          ${operacion.calculos.comision_proveedor.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                      </div>
                    </div>

                    <div className="bg-slate-100 rounded-lg p-6 border-2 border-slate-300">
                      <Label className="text-slate-600 text-sm">Total Egreso MBco (Capital + Comisión Proveedor)</Label>
                      <p className="text-3xl font-bold text-slate-800">
                        ${operacion.calculos.total_egreso.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                    </div>

                    {puedeConfirmar && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
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
                        <p className="text-amber-800">
                          Completa los pasos anteriores para calcular los montos.
                        </p>
                        <p className="text-sm text-amber-600 mt-2">
                          Necesitas: comprobantes válidos y datos del titular.
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
    </div>
  );
};

export default OperacionDetalle;