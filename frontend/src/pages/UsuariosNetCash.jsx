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
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <div className="flex gap-2 mb-4">
          <Button
            variant="outline"
            onClick={() => navigate('/')}
            className="bg-white hover:bg-slate-50 text-slate-700"
          >
            <HomeIcon className="h-4 w-4 mr-2" />
            Inicio
          </Button>
          <Button
            variant="ghost"
            onClick={() => navigate('/dashboard')}
            className="text-slate-600 hover:text-slate-800"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver al Dashboard
          </Button>
        </div>
        <div className="flex items-center gap-3 mb-2">
          <Users className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Usuarios NetCash</h1>
        </div>
        <p className="text-gray-600">
          Catálogo de usuarios del sistema con roles y permisos
        </p>
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
  );
};

export default UsuariosNetCash;
