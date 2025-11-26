import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, BarChart3, Users, Shield, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      {/* Hero Section */}
      <div className="container mx-auto px-6 py-20">
        <div className="flex flex-col items-center text-center animate-fade-in">
          <div className="mb-8">
            <div className="inline-block bg-blue-100 rounded-full px-6 py-2 mb-6">
              <span className="text-blue-700 font-semibold text-sm tracking-wide">ASISTENTE NETCASH MBCO</span>
            </div>
          </div>
          
          <h1 
            className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 leading-tight"
            style={{ fontFamily: 'Cormorant Garamond, serif' }}
            data-testid="home-title"
          >
            Gestión Inteligente de
            <br />
            <span className="text-blue-600">Operaciones NetCash</span>
          </h1>
          
          <p className="text-lg sm:text-xl text-slate-600 max-w-3xl mb-12 leading-relaxed">
            Automatiza el procesamiento de depósitos, validación de comprobantes y generación de ligas NetCash.
            Todo en una plataforma centralizada y eficiente.
          </p>

          <div className="flex gap-4 flex-wrap justify-center">
            <Button
              data-testid="dashboard-btn"
              onClick={() => navigate('/dashboard')}
              size="lg"
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-6 text-lg rounded-xl shadow-lg hover:shadow-xl transition-all"
            >
              <BarChart3 className="mr-2 h-5 w-5" />
              Ir al Dashboard
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="about-btn"
              variant="outline"
              size="lg"
              className="border-2 border-blue-600 text-blue-600 hover:bg-blue-50 px-8 py-6 text-lg rounded-xl"
            >
              <FileText className="mr-2 h-5 w-5" />
              Documentación
            </Button>
          </div>
        </div>

        {/* Features Section */}
        <div className="grid md:grid-cols-3 gap-8 mt-24 animate-slide-in">
          <FeatureCard
            icon={<FileText className="h-10 w-10 text-blue-600" />}
            title="OCR Inteligente"
            description="Lectura automática de comprobantes bancarios con validación de cuenta y beneficiario."
          />
          
          <FeatureCard
            icon={<BarChart3 className="h-10 w-10 text-emerald-600" />}
            title="Cálculos Precisos"
            description="Cálculo automático de capital, comisiones de cliente y comisiones de proveedor."
          />
          
          <FeatureCard
            icon={<Users className="h-10 w-10 text-purple-600" />}
            title="Gestión de Flujo"
            description="Seguimiento completo desde el depósito del cliente hasta la entrega de ligas."
          />
        </div>

        {/* Info Section */}
        <div className="mt-24 bg-white rounded-3xl p-12 shadow-xl">
          <div className="flex items-start gap-6">
            <div className="bg-blue-100 rounded-2xl p-4">
              <Shield className="h-8 w-8 text-blue-600" />
            </div>
            <div>
              <h3 className="text-2xl font-bold mb-4" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                Cuenta de Depósito Autorizada
              </h3>
              <div className="space-y-2 text-slate-700">
                <p><strong>Razón social:</strong> JARDINERIA Y COMERCIO THABYETHA SA DE CV</p>
                <p><strong>Banco:</strong> STP</p>
                <p><strong>CLABE:</strong> 646180139409481462</p>
              </div>
              <p className="mt-4 text-sm text-slate-500">
                Todos los depósitos de clientes NetCash deben realizarse a esta cuenta.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-12 text-center text-slate-600 border-t border-slate-200 bg-white/50">
        <p className="text-sm">
          © 2025 MBco - Asistente NetCash | Fase 1: Módulo Cliente + OCR + Cálculos Básicos
        </p>
      </footer>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => {
  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all hover:-translate-y-2">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-bold mb-3" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
        {title}
      </h3>
      <p className="text-slate-600 leading-relaxed">
        {description}
      </p>
    </div>
  );
};

export default Home;