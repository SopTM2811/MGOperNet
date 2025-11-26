import React from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ComprobantesUpload from './ComprobantesUpload';

const ComprobantesModal = ({ operacion, onClose, onActualizado }) => {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                Subir Comprobantes
              </h2>
              <p className="text-sm text-slate-600 mt-1">
                Operación: <code className="bg-slate-100 px-2 py-0.5 rounded">{operacion.id.substring(0, 8)}...</code>
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600"
              data-testid="close-comprobantes-modal-btn"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <ComprobantesUpload
            operacionId={operacion.id}
            comprobantes={operacion.comprobantes || []}
            onComprobantesActualizados={() => {
              if (onActualizado) onActualizado();
            }}
          />

          <div className="mt-6 flex justify-end">
            <Button
              onClick={onClose}
              variant="outline"
              data-testid="close-modal-btn"
            >
              Cerrar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComprobantesModal;
