import React, { useState } from 'react';
import axios from 'axios';
import { X, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import ClienteSelector from './ClienteSelector';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const NuevaOperacionModal = ({ onClose, onSuccess }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [clienteSeleccionado, setClienteSeleccionado] = useState(null);
  const [comisionOperacion, setComisionOperacion] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!clienteSeleccionado) {
      toast.error('Debes seleccionar un cliente');
      return;
    }
    
    try {
      setLoading(true);
      
      const payload = {
        id_cliente: clienteSeleccionado.id,
        porcentaje_comision_usado: comisionOperacion || clienteSeleccionado.porcentaje_comision_cliente
      };
      
      const response = await axios.post(`${API}/operaciones`, payload);
      
      toast.success('Operación creada exitosamente');
      
      // Navegar a la página de detalle
      navigate(`/operacion/${response.data.id}`);
      
      if (onSuccess) onSuccess();
    } catch (error) {
      console.error('Error creando operación:', error);
      toast.error(error.response?.data?.detail || 'Error al crear operación');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Nueva Operación NetCash
            </h2>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600"
              data-testid="close-modal-btn"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="cliente_nombre">Nombre del Cliente *</Label>
              <Input
                id="cliente_nombre"
                value={formData.cliente_nombre}
                onChange={(e) => setFormData({...formData, cliente_nombre: e.target.value})}
                placeholder="Nombre completo"
                required
                data-testid="cliente-nombre-input"
              />
            </div>

            <div>
              <Label htmlFor="cliente_telegram_id">Telegram ID</Label>
              <Input
                id="cliente_telegram_id"
                value={formData.cliente_telegram_id}
                onChange={(e) => setFormData({...formData, cliente_telegram_id: e.target.value})}
                placeholder="ID de Telegram (opcional)"
                data-testid="cliente-telegram-input"
              />
            </div>

            <div>
              <Label htmlFor="cliente_telefono">Teléfono</Label>
              <Input
                id="cliente_telefono"
                value={formData.cliente_telefono}
                onChange={(e) => setFormData({...formData, cliente_telefono: e.target.value})}
                placeholder="Teléfono (opcional)"
                data-testid="cliente-telefono-input"
              />
            </div>

            <div>
              <Label htmlFor="propietario">Propietario de la Operación *</Label>
              <Select
                value={formData.propietario}
                onValueChange={(value) => setFormData({...formData, propietario: value})}
              >
                <SelectTrigger data-testid="propietario-select">
                  <SelectValue placeholder="Selecciona propietario" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="D">Daniel</SelectItem>
                  <SelectItem value="S">Samuel</SelectItem>
                  <SelectItem value="R">Ramón</SelectItem>
                  <SelectItem value="M">MBco / Market Business</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
              <p className="text-sm text-blue-800">
                <strong>Siguiente paso:</strong> Después de crear la operación, podrás subir los comprobantes de depósito.
              </p>
            </div>

            <div className="flex gap-3 mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                className="flex-1"
                data-testid="cancel-btn"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                data-testid="create-operation-btn"
              >
                {loading ? 'Creando...' : 'Crear Operación'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default NuevaOperacionModal;