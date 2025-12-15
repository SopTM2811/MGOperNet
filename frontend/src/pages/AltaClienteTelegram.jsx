import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ArrowLeft, Home as HomeIcon } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AltaClienteTelegram = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    nombre: '',
    telegram_id: '',
    comision_pct: '1.0'
  });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validaciones básicas
    if (!formData.email || !formData.nombre || !formData.telegram_id || !formData.comision_pct) {
      alert('Todos los campos son obligatorios');
      return;
    }

    const comision = parseFloat(formData.comision_pct);
    if (isNaN(comision) || comision < 0.375) {
      alert('La comisión debe ser al menos 0.375%');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/api/telegram/alta_desde_web`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          nombre: formData.nombre,
          telegram_id: formData.telegram_id,
          comision_pct: comision
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Error al vincular cliente');
      }
      
      alert('✅ Cliente vinculado y mensaje enviado por Telegram');
      
      // Limpiar formulario
      setFormData({
        email: '',
        nombre: '',
        telegram_id: '',
        comision_pct: '1.0'
      });

    } catch (error) {
      console.error('Error:', error);
      alert(error.message || 'Error al vincular cliente');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white py-4 sm:py-8">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl">
        {/* Header - Mismo diseño que Dashboard */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 sm:mb-12">
          <div>
            <h1 
              className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-1 sm:mb-2 tracking-tight"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Alta Cliente Telegram
            </h1>
            <p className="text-sm sm:text-base text-slate-600 font-light">Vincula un cliente con su Telegram ID</p>
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

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Datos del Cliente</CardTitle>
            <p className="text-slate-600 text-sm mt-2">
              Completa los datos para vincular el cliente y enviar mensaje de bienvenida automáticamente
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="email">Correo electrónico *</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="cliente@ejemplo.com"
                  required
                  disabled={loading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="nombre">Nombre completo *</Label>
                <Input
                  id="nombre"
                  name="nombre"
                  type="text"
                  value={formData.nombre}
                  onChange={handleChange}
                  placeholder="Juan Pérez García"
                  required
                  disabled={loading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="telegram_id">Telegram ID *</Label>
                <Input
                  id="telegram_id"
                  name="telegram_id"
                  type="text"
                  value={formData.telegram_id}
                  onChange={handleChange}
                  placeholder="123456789"
                  required
                  disabled={loading}
                />
                <p className="text-xs text-slate-500">
                  El ID numérico del usuario en Telegram (no el @username)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="comision_pct">Comisión (%) *</Label>
                <Input
                  id="comision_pct"
                  name="comision_pct"
                  type="number"
                  step="0.001"
                  min="0.375"
                  value={formData.comision_pct}
                  onChange={handleChange}
                  placeholder="1.0"
                  required
                  disabled={loading}
                />
                <p className="text-xs text-slate-500">
                  Comisión mínima: 0.375%
                </p>
              </div>

              <div className="pt-4 border-t">
                <Button 
                  type="submit" 
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium"
                  disabled={loading}
                >
                  {loading ? 'Procesando...' : 'Vincular y enviar bienvenida'}
                </Button>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
                <p className="text-sm text-blue-800">
                  <strong>Nota:</strong> Al enviar este formulario:
                </p>
                <ul className="text-sm text-blue-700 mt-2 space-y-1 list-disc list-inside">
                  <li>Se creará o actualizará el cliente con la comisión especificada</li>
                  <li>Se vinculará el Telegram ID al cliente</li>
                  <li>Se enviará un mensaje de bienvenida al usuario por Telegram</li>
                  <li>El usuario podrá operar inmediatamente desde el bot</li>
                </ul>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AltaClienteTelegram;
