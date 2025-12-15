import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, FileText, User, CreditCard, Hash, Calendar, CheckCircle, Clock, AlertCircle, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SolicitudNetCashDetalle = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [solicitud, setSolicitud] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    cargarSolicitud();
  }, [id]);

  const cargarSolicitud = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/netcash/solicitudes/${id}`);
      if (response.data.success) {
        setSolicitud(response.data.solicitud);
      }
    } catch (error) {
      console.error('Error cargando solicitud:', error);
      toast.error('Error al cargar la solicitud');
    } finally {
      setLoading(false);
    }
  };

  const getEstadoBadge = (estado) => {
    const estadoMap = {
      'borrador': { color: 'bg-slate-500', label: 'Borrador', icon: Clock },
      'pendiente_comprobantes': { color: 'bg-amber-500', label: 'Esperando Comprobantes', icon: Clock },
      'pendiente_datos': { color: 'bg-blue-500', label: 'Esperando Datos', icon: AlertCircle },
      'pendiente_confirmacion': { color: 'bg-purple-500', label: 'Por Confirmar', icon: AlertCircle },
      'pendiente_validacion_admin': { color: 'bg-orange-500', label: 'Validación Admin', icon: AlertCircle },
      'lista_para_mbco': { color: 'bg-green-500', label: 'Lista para MBco', icon: CheckCircle },
      'enviada_tesoreria': { color: 'bg-indigo-500', label: 'En Tesorería', icon: Clock },
      'completada': { color: 'bg-green-600', label: 'Completada', icon: CheckCircle },
      'rechazada': { color: 'bg-red-500', label: 'Rechazada', icon: AlertCircle },
      'cancelada': { color: 'bg-red-400', label: 'Cancelada', icon: AlertCircle },
    };
    
    const config = estadoMap[estado] || { color: 'bg-slate-400', label: estado, icon: Clock };
    const Icon = config.icon;
    
    return (
      <Badge className={`${config.color} text-white flex items-center gap-1`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const formatFecha = (fecha) => {
    if (!fecha) return 'N/A';
    try {
      return new Date(fecha).toLocaleString('es-MX', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'N/A';
    }
  };

  const formatMonto = (monto) => {
    if (!monto) return '$0.00';
    return `$${Number(monto).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-500">Cargando solicitud...</div>
      </div>
    );
  }

  if (!solicitud) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 mx-auto mb-4 text-red-400" />
          <p className="text-slate-600">Solicitud no encontrada</p>
          <Button className="mt-4" onClick={() => navigate('/dashboard')}>
            Volver al Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const montoTotal = solicitud.monto_depositado_cliente || 
    solicitud.comprobantes?.reduce((sum, c) => sum + (c.monto_detectado || c.monto || 0), 0) || 0;

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            onClick={() => navigate('/dashboard')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver al Dashboard
          </Button>

          <div className="flex items-center gap-4 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-800">
              Solicitud Telegram
            </h1>
            <Badge variant="outline" className="border-blue-400 text-blue-600">
              📱 Origen: Telegram
            </Badge>
            {solicitud.modo_captura === 'manual_por_fallo_ocr' && (
              <Badge variant="outline" className="border-amber-400 text-amber-600">
                ✋ Captura Manual
              </Badge>
            )}
            {getEstadoBadge(solicitud.estado)}
          </div>

          <code className="text-sm font-mono bg-slate-200 px-2 py-1 rounded mt-2 inline-block">
            ID: {solicitud.id}
          </code>
          {solicitud.folio_mbco && (
            <Badge className="ml-2 bg-blue-600 text-white">
              {solicitud.folio_mbco}
            </Badge>
          )}
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Información del Cliente */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Información del Cliente
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-slate-500 text-sm">Nombre del Cliente</Label>
                <p className="font-medium text-lg">{solicitud.cliente_nombre || 'No especificado'}</p>
              </div>
              <div>
                <Label className="text-slate-500 text-sm">IDMEX Cliente</Label>
                <p className="font-mono">{solicitud.idmex || 'No especificado'}</p>
              </div>
              <div>
                <Label className="text-slate-500 text-sm">Telegram ID</Label>
                <p className="font-mono text-sm">{solicitud.telegram_id || 'N/A'}</p>
              </div>
              <div>
                <Label className="text-slate-500 text-sm">Fecha de Creación</Label>
                <p>{formatFecha(solicitud.created_at)}</p>
              </div>
            </CardContent>
          </Card>

          {/* Información del Beneficiario */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" />
                Beneficiario / Titular
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-slate-500 text-sm">Nombre del Beneficiario</Label>
                <p className="font-medium text-lg">{solicitud.beneficiario_reportado || 'No especificado'}</p>
              </div>
              <div>
                <Label className="text-slate-500 text-sm">IDMEX Beneficiario</Label>
                <p className="font-mono">
                  {solicitud.idmex_beneficiario_declarado || solicitud.idmex_reportado || 'No especificado'}
                </p>
              </div>
              <div>
                <Label className="text-slate-500 text-sm">Número de Ligas</Label>
                <p className="font-bold text-xl text-blue-600">{solicitud.cantidad_ligas_reportada || 0}</p>
              </div>
            </CardContent>
          </Card>

          {/* Información Financiera */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Hash className="h-5 w-5" />
                Información Financiera
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <Label className="text-slate-500 text-sm">Monto Total Depositado</Label>
                <p className="font-bold text-3xl text-blue-700">{formatMonto(montoTotal)}</p>
              </div>
              {solicitud.comision_cliente && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                    <Label className="text-slate-500 text-xs">Comisión Cliente</Label>
                    <p className="font-bold text-amber-700">{formatMonto(solicitud.comision_cliente)}</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                    <Label className="text-slate-500 text-xs">Capital a Dispersar</Label>
                    <p className="font-bold text-green-700">{formatMonto(montoTotal - solicitud.comision_cliente)}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Comprobantes */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Comprobantes ({solicitud.comprobantes?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {solicitud.comprobantes?.length > 0 ? (
                <div className="space-y-2">
                  {solicitud.comprobantes.map((comp, idx) => (
                    <div 
                      key={idx} 
                      className={`p-3 rounded-lg border ${comp.es_valido ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {comp.es_valido ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <AlertCircle className="h-4 w-4 text-red-600" />
                          )}
                          <span className="text-sm font-medium">
                            Comprobante #{idx + 1}
                          </span>
                        </div>
                        <span className="font-bold">
                          {formatMonto(comp.monto_detectado || comp.monto)}
                        </span>
                      </div>
                      {comp.banco_emisor && (
                        <p className="text-xs text-slate-500 mt-1">Banco: {comp.banco_emisor}</p>
                      )}
                      {comp.es_duplicado && (
                        <Badge variant="destructive" className="mt-1">Duplicado</Badge>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-slate-500">
                  <FileText className="h-8 w-8 mx-auto mb-2 text-slate-300" />
                  <p>Sin comprobantes registrados</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Información adicional de modo manual */}
        {solicitud.modo_captura === 'manual_por_fallo_ocr' && (
          <Card className="mt-6 border-amber-300">
            <CardHeader className="bg-amber-50">
              <CardTitle className="flex items-center gap-2 text-amber-700">
                <MessageSquare className="h-5 w-5" />
                Información de Captura Manual
              </CardTitle>
              <CardDescription className="text-amber-600">
                Esta solicitud fue capturada manualmente debido a fallo en OCR
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-slate-500 text-sm">Razón del Fallo OCR</Label>
                  <p className="text-sm">{solicitud.razon_fallo_ocr || 'No especificada'}</p>
                </div>
                <div>
                  <Label className="text-slate-500 text-sm">Fecha de Captura Manual</Label>
                  <p className="text-sm">{formatFecha(solicitud.timestamp_captura_manual)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default SolicitudNetCashDetalle;
