import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Users, Mail, MessageSquare, Shield, CheckCircle, XCircle, Home as HomeIcon, ArrowLeft } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const UsuariosNetCash = () => {
  const navigate = useNavigate();
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    cargarUsuarios();
  }, []);

  const cargarUsuarios = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/api/netcash/usuarios/`);
      
      if (!response.ok) {
        throw new Error('Error al cargar usuarios');
      }
      
      const data = await response.json();
      setUsuarios(data);
      setError(null);
    } catch (err) {
      console.error('Error cargando usuarios:', err);
      setError('No se pudieron cargar los usuarios. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  const getRolBadgeColor = (rol) => {
    const colores = {
      'master': 'bg-purple-500 text-white',
      'admin_netcash': 'bg-blue-500 text-white',
      'tesoreria': 'bg-green-500 text-white',
      'sup_tesoreria': 'bg-green-600 text-white',
      'operador_proveedor': 'bg-orange-500 text-white',
      'sup_proveedor': 'bg-orange-600 text-white',
      'socio_mbco': 'bg-indigo-500 text-white',
      'dueno_dns': 'bg-pink-500 text-white',
      'apoyo_cliente': 'bg-cyan-500 text-white'
    };
    return colores[rol] || 'bg-gray-500 text-white';
  };

  const getRolLabel = (rol) => {
    const labels = {
      'master': 'Master',
      'admin_netcash': 'Admin NetCash',
      'tesoreria': 'Tesorería',
      'sup_tesoreria': 'Supervisor Tesorería',
      'operador_proveedor': 'Operador Proveedor',
      'sup_proveedor': 'Supervisor Proveedor',
      'socio_mbco': 'Socio MBco',
      'dueno_dns': 'Dueño DNS',
      'apoyo_cliente': 'Apoyo Cliente'
    };
    return labels[rol] || rol;
  };

  const getPermisosActivos = (permisos) => {
    if (!permisos) return [];
    return Object.entries(permisos)
      .filter(([key, value]) => value === true)
      .map(([key]) => key);
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-8">
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-600">Cargando usuarios...</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

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
              Usuarios NetCash
            </h1>
            <p className="text-sm sm:text-base text-slate-600 font-light">Catálogo de usuarios del sistema con roles y permisos</p>
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

        {error && (
          <Alert className="mb-6 bg-red-50 border-red-200">
            <AlertDescription className="text-red-800">
              {error}
            </AlertDescription>
          </Alert>
        )}

      <div className="grid gap-4">
        {usuarios.map((usuario) => {
          const permisosActivos = getPermisosActivos(usuario.permisos);
          
          return (
            <Card key={usuario.id_usuario} className="hover:shadow-lg transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                      <Users className="w-6 h-6 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold text-gray-900">
                        {usuario.nombre}
                      </h3>
                      <Badge className={`mt-1 ${getRolBadgeColor(usuario.rol_negocio)}`}>
                        <Shield className="w-3 h-3 mr-1" />
                        {getRolLabel(usuario.rol_negocio)}
                      </Badge>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {usuario.activo ? (
                      <Badge className="bg-green-100 text-green-800">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Activo
                      </Badge>
                    ) : (
                      <Badge className="bg-red-100 text-red-800">
                        <XCircle className="w-3 h-3 mr-1" />
                        Inactivo
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4 mb-4">
                  <div className="flex items-center gap-2 text-gray-700">
                    <MessageSquare className="w-4 h-4 text-blue-500" />
                    <span className="text-sm font-medium">Telegram ID:</span>
                    <span className="text-sm">
                      {usuario.telegram_id || (
                        <span className="text-gray-400 italic">No configurado</span>
                      )}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 text-gray-700">
                    <Mail className="w-4 h-4 text-blue-500" />
                    <span className="text-sm font-medium">Email:</span>
                    <span className="text-sm">
                      {usuario.email || (
                        <span className="text-gray-400 italic">No configurado</span>
                      )}
                    </span>
                  </div>
                </div>

                {permisosActivos.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">
                      Permisos activos:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {permisosActivos.map((permiso) => (
                        <Badge 
                          key={permiso} 
                          variant="outline"
                          className="text-xs bg-blue-50 border-blue-200 text-blue-700"
                        >
                          {permiso.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {usuarios.length === 0 && !loading && (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg">
              No hay usuarios registrados en el sistema
            </p>
          </CardContent>
        </Card>
      )}
      </div>
    </div>
  );
};

export default UsuariosNetCash;
