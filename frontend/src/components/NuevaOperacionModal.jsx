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
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
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

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Selector de Cliente */}
            <div>
              <ClienteSelector
                onClienteSeleccionado={setClienteSeleccionado}
                clienteSeleccionado={clienteSeleccionado}
              />
            </div>

            {/* Comisión específica de esta operación */}
            {clienteSeleccionado && (
              <div className="bg-slate-50 rounded-lg p-4">
                <Label htmlFor="comision_operacion">Comisión de esta operación (%)</Label>
                <Input
                  id="comision_operacion"
                  type="number"
                  step="0.01"
                  min="0"
                  value={comisionOperacion === null ? clienteSeleccionado.porcentaje_comision_cliente : comisionOperacion}
                  onChange={(e) => setComisionOperacion(parseFloat(e.target.value))}
                  data-testid="operation-commission-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Por defecto se usa la comisión del cliente ({clienteSeleccionado.porcentaje_comision_cliente}%).
                  Puedes modificarla solo para esta operación.
                </p>
              </div>
            )}

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
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
                disabled={loading || !clienteSeleccionado}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                data-testid="create-operation-btn"
              >
                {loading ? 'Creando...' : (
                  <>
                    Crear Operación
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default NuevaOperacionModal;