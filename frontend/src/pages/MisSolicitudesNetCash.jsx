import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, FileText, Clock, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MisSolicitudesNetCash = () => {
  const navigate = useNavigate();
  const [solicitudes, setSolicitudes] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Por ahora usamos un cliente de prueba - esto debería venir de autenticación
  const clienteId = "d9115936-733e-4598-a23c-2ae7633216f9"; // Cliente de prueba

  useEffect(() => {
    cargarSolicitudes();
  }, []);

  const cargarSolicitudes = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/netcash/solicitudes/cliente/${clienteId}`);
      
      if (response.data.success) {
        setSolicitudes(response.data.solicitudes);
      }
    } catch (error) {
      console.error('Error cargando solicitudes:', error);
      toast.error('Error al cargar solicitudes NetCash');
    } finally {
      setLoading(false);
    }
  };

  const getEstadoBadge = (estado) => {
    const estadoMap = {
      'borrador': { variant: 'secondary', label: 'Borrador', icon: Clock, color: 'slate' },
      'lista_para_mbc': { variant: 'default', label: 'Lista para MBco', icon: CheckCircle, color: 'green' },
      'rechazada': { variant: 'destructive', label: 'Rechazada', icon: XCircle, color: 'red' },
      'en_proceso_mbc': { variant: 'default', label: 'En Proceso', icon: Clock, color: 'blue' }
    };

    const config = estadoMap[estado] || { variant: 'secondary', label: estado, icon: FileText, color: 'gray' };
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

  const formatMonto = (monto) => {
    if (!monto || monto === 0) return '-';
    return `$${monto.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="min-h-screen bg-white py-8">
      <div className="container mx-auto px-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 
              className="text-4xl font-bold mb-2 tracking-tight"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Mis Solicitudes NetCash
            </h1>
            <p className="text-slate-600 font-light">
              Consulta el estado de tus operaciones NetCash
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => navigate('/')}
            className="border-slate-300"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver al inicio
          </Button>
        </div>

        {/* Lista de Solicitudes */}
        <Card>
          <CardHeader>
            <CardTitle>Mis Operaciones</CardTitle>
            <CardDescription>
              {solicitudes.length} solicitud(es) encontrada(s)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-12">
                <div className="animate-pulse text-slate-400">Cargando solicitudes...</div>
              </div>
            ) : solicitudes.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <FileText className="h-12 w-12 mx-auto mb-4 text-slate-300" />
                <p className="text-lg mb-2">No tienes solicitudes NetCash</p>
                <p className="text-sm">Crea tu primera operación desde Telegram</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-slate-50">
                      <th className="text-left p-3 font-semibold text-sm">Folio</th>
                      <th className="text-left p-3 font-semibold text-sm">Fecha</th>
                      <th className="text-left p-3 font-semibold text-sm">Beneficiario</th>
                      <th className="text-right p-3 font-semibold text-sm">Total Depósitos</th>
                      <th className="text-right p-3 font-semibold text-sm">Comisión NetCash</th>
                      <th className="text-right p-3 font-semibold text-sm">Monto en Ligas</th>
                      <th className="text-center p-3 font-semibold text-sm">Ligas</th>
                      <th className="text-center p-3 font-semibold text-sm">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solicitudes.map((sol) => (
                      <tr key={sol.id} className="border-b hover:bg-slate-50 transition-colors">
                        <td className="p-3">
                          {sol.folio_mbco ? (
                            <Badge className="bg-blue-600 text-white font-semibold">
                              {sol.folio_mbco}
                            </Badge>
                          ) : (
                            <span className="text-slate-400 text-sm">Sin folio</span>
                          )}
                        </td>
                        <td className="p-3 text-sm text-slate-600">
                          {formatFecha(sol.created_at)}
                        </td>
                        <td className="p-3 text-sm font-medium">
                          {sol.beneficiario_reportado || '-'}
                        </td>
                        <td className="p-3 text-sm text-right font-semibold text-green-600">
                          {formatMonto(sol.total_comprobantes_validos)}
                        </td>
                        <td className="p-3 text-sm text-right text-slate-600">
                          {formatMonto(sol.comision_cliente)}
                          {sol.porcentaje_comision_cliente && (
                            <span className="text-xs text-slate-400 ml-1">
                              ({sol.porcentaje_comision_cliente}%)
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-sm text-right font-semibold text-blue-600">
                          {formatMonto(sol.monto_ligas)}
                        </td>
                        <td className="p-3 text-center">
                          <Badge variant="outline">
                            {sol.cantidad_ligas_reportada || 0}
                          </Badge>
                        </td>
                        <td className="p-3 text-center">
                          {getEstadoBadge(sol.estado)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info adicional */}
        <div className="mt-6 text-sm text-slate-500 text-center">
          <p>💡 Para crear una nueva operación NetCash, usa el bot de Telegram</p>
        </div>
      </div>
    </div>
  );
};

export default MisSolicitudesNetCash;
