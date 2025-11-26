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
            {clienteSeleccionado && (\n              <div className=\"bg-slate-50 rounded-lg p-4\">\n                <Label htmlFor=\"comision_operacion\">Comisión de esta operación (%)</Label>\n                <Input\n                  id=\"comision_operacion\"\n                  type=\"number\"\n                  step=\"0.01\"\n                  min=\"0\"\n                  value={comisionOperacion === null ? clienteSeleccionado.porcentaje_comision_cliente : comisionOperacion}\n                  onChange={(e) => setComisionOperacion(parseFloat(e.target.value))}\n                  data-testid=\"operation-commission-input\"\n                />\n                <p className=\"text-xs text-slate-500 mt-1\">\n                  Por defecto se usa la comisión del cliente ({clienteSeleccionado.porcentaje_comision_cliente}%).\n                  Puedes modificarla solo para esta operación.\n                </p>\n              </div>\n            )}\n\n            <div className=\"bg-blue-50 border border-blue-200 rounded-lg p-4\">\n              <p className=\"text-sm text-blue-800\">\n                <strong>Siguiente paso:</strong> Después de crear la operación, podrás subir los comprobantes de depósito.\n              </p>\n            </div>\n\n            <div className=\"flex gap-3 mt-6\">\n              <Button\n                type=\"button\"\n                variant=\"outline\"\n                onClick={onClose}\n                className=\"flex-1\"\n                data-testid=\"cancel-btn\"\n              >\n                Cancelar\n              </Button>\n              <Button\n                type=\"submit\"\n                disabled={loading || !clienteSeleccionado}\n                className=\"flex-1 bg-blue-600 hover:bg-blue-700\"\n                data-testid=\"create-operation-btn\"\n              >\n                {loading ? 'Creando...' : (\n                  <>\n                    Crear Operación\n                    <ArrowRight className=\"ml-2 h-4 w-4\" />\n                  </>\n                )}\n              </Button>\n            </div>\n          </form>\n        </div>\n      </div>\n    </div>\n  );\n};

export default NuevaOperacionModal;