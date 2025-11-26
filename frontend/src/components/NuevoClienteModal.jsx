import React, { useState } from 'react';
import axios from 'axios';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const NuevoClienteModal = ({ onClose, onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    nombre: '',
    telefono: '',
    email: '',
    rfc: '',
    notas: '',
    propietario: 'M',
    porcentaje_comision_cliente: 0.65,
    estado: 'activo',
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.nombre.trim()) {
      toast.error('El nombre es obligatorio');
      return;
    }
    
    if (!formData.telefono.trim()) {
      toast.error('El teléfono es obligatorio');
      return;
    }
    
    try {
      setLoading(true);
      
      const payload = {
        nombre: formData.nombre.trim(),
        telefono: formData.telefono.trim(),
        email: formData.email.trim() || undefined,
        rfc: formData.rfc.trim() || undefined,
        notas: formData.notas.trim() || undefined,
        propietario: formData.propietario,
        porcentaje_comision_cliente: parseFloat(formData.porcentaje_comision_cliente),
        estado: formData.estado,
      };
      
      await axios.post(`${API}/clientes`, payload);
      
      toast.success('✅ Cliente registrado correctamente');
      
      if (onSuccess) onSuccess();
      onClose();
    } catch (error) {
      console.error('Error creando cliente:', error);
      toast.error(error.response?.data?.detail || 'Error al crear cliente');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Nuevo Cliente
            </h2>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Nombre */}
            <div>
              <Label htmlFor="nombre">Nombre completo o Razón social *</Label>
              <Input
                id="nombre"
                value={formData.nombre}
                onChange={(e) => handleChange('nombre', e.target.value)}
                placeholder="Ej: Juan Pérez o Empresa SA de CV"
                required
              />
            </div>

            {/* Teléfono */}
            <div>
              <Label htmlFor="telefono">Teléfono *</Label>
              <Input
                id="telefono"
                value={formData.telefono}
                onChange={(e) => handleChange('telefono', e.target.value)}
                placeholder="Ej: 3312345678"
                required
              />
            </div>

            {/* RFC (opcional) */}
            <div>
              <Label htmlFor="rfc">RFC (opcional)</Label>
              <Input
                id="rfc"
                value={formData.rfc}
                onChange={(e) => handleChange('rfc', e.target.value)}
                placeholder="Ej: XAXX010101000"
              />
            </div>

            {/* Email (opcional) */}
            <div>
              <Label htmlFor="email">Correo electrónico (opcional)</Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="cliente@ejemplo.com"
              />
            </div>

            {/* Estado */}
            <div>
              <Label htmlFor="estado">Estado</Label>
              <Select 
                value={formData.estado} 
                onValueChange={(value) => handleChange('estado', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pendiente_validacion">Pendiente Validación</SelectItem>
                  <SelectItem value="activo">Activo</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-500 mt-1">
                Solo clientes "Activos" pueden crear operaciones
              </p>
            </div>

            {/* Propietario */}
            <div>
              <Label htmlFor="propietario">Propietario</Label>
              <Select 
                value={formData.propietario} 
                onValueChange={(value) => handleChange('propietario', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="M">Market & Business (M)</SelectItem>
                  <SelectItem value="D">Daniel (D)</SelectItem>
                  <SelectItem value="S">Samuel (S)</SelectItem>
                  <SelectItem value="R">Ramón (R)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Comisión */}
            <div>
              <Label htmlFor="comision">Comisión del cliente (%)</Label>
              <Input
                id="comision"
                type="number"
                step="0.01"
                value={formData.porcentaje_comision_cliente}
                onChange={(e) => handleChange('porcentaje_comision_cliente', e.target.value)}
                placeholder="0.65"
              />
            </div>

            {/* Notas (opcional) */}
            <div>
              <Label htmlFor="notas">Notas / Comentarios (opcional)</Label>
              <textarea
                id="notas"
                value={formData.notas}
                onChange={(e) => handleChange('notas', e.target.value)}
                placeholder="Cualquier información adicional sobre el cliente"
                className="w-full min-h-[80px] p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Botones */}
            <div className="flex gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                className="flex-1"
                disabled={loading}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                className="flex-1"
                disabled={loading}
              >
                {loading ? 'Guardando...' : 'Guardar Cliente'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default NuevoClienteModal;
