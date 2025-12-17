import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, BarChart3, Users, Shield, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Section */}
      <div className="container mx-auto px-8 py-24 lg:py-32">
        <div className="flex flex-col items-center text-center animate-fade-in max-w-5xl mx-auto">
          <div className="mb-12">
            <div className="inline-block bg-blue-50 rounded-full px-5 py-2 mb-8 border border-blue-100">
              <span className="text-blue-700 font-medium text-sm tracking-tight">ASISTENTE NETCASH MBCO</span>
            </div>
          </div>
          
          <h1 
            className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-8 leading-[1.1] tracking-tight"
            style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            data-testid="home-title"
          >
            Gestión Inteligente de
            <br />
            <span className="text-blue-600">Operaciones NetCash</span>
          </h1>
          
          <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mb-14 leading-relaxed font-light">
            Automatiza el procesamiento de depósitos, validación de comprobantes y generación de ligas NetCash.
            Todo en una plataforma centralizada y eficiente.
          </p>

          <div className="flex gap-4 flex-wrap justify-center">
            <Button
              data-testid="dashboard-btn"
              onClick={() => navigate('/dashboard')}
              size="lg"
              className="bg-blue-600 hover:bg-blue-700 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <BarChart3 className="mr-2 h-5 w-5" />
              Operaciones
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="clientes-btn"
              onClick={() => navigate('/clientes')}
              size="lg"
              className="bg-slate-700 hover:bg-slate-800 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <Users className="mr-2 h-5 w-5" />
              Clientes
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="mbcontrol-btn"
              onClick={() => navigate('/pendientes-mbcontrol')}
              size="lg"
              className="bg-amber-600 hover:bg-amber-700 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <Shield className="mr-2 h-5 w-5" />
              MBControl
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="alta-telegram-btn"
              onClick={() => navigate('/alta-cliente-telegram')}
              size="lg"
              className="bg-green-600 hover:bg-green-700 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <Users className="mr-2 h-5 w-5" />
              Alta Telegram
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="solicitudes-netcash-btn"
              onClick={() => navigate('/mis-solicitudes-netcash')}
              size="lg"
              className="bg-purple-600 hover:bg-purple-700 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <FileText className="mr-2 h-5 w-5" />
              Mis Solicitudes
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            <Button
              data-testid="beneficiarios-btn"
              onClick={() => navigate('/beneficiarios')}
              size="lg"
              className="bg-teal-600 hover:bg-teal-700 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <Users className="mr-2 h-5 w-5" />
              Beneficiarios
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            
            {/* TODO: cuando tengamos usuario logueado, mostrar este botón solo si 
                usuario.permisos.puede_ver_usuarios === true */}
            <Button
              data-testid="usuarios-netcash-btn"
              onClick={() => navigate('/usuarios-netcash')}
              size="lg"
              className="bg-gray-700 hover:bg-gray-800 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
            >
              <Users className="mr-2 h-5 w-5" />
              Usuarios
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Features Section */}
        <div className="grid md:grid-cols-3 gap-6 mt-32 max-w-6xl mx-auto">
          <FeatureCard
            icon={<FileText className="h-8 w-8 text-blue-600" />}
            title="OCR Inteligente"
            description="Lectura automática de comprobantes bancarios con validación de cuenta y beneficiario."
          />
          
          <FeatureCard
            icon={<BarChart3 className="h-8 w-8 text-blue-600" />}
            title="Cálculos Precisos"
            description="Cálculo automático de capital, comisiones de cliente y comisiones de proveedor."
          />
          
          <FeatureCard
            icon={<Users className="h-8 w-8 text-blue-600" />}
            title="Gestión de Flujo"
            description="Seguimiento completo desde el depósito del cliente hasta la entrega de ligas."
          />
        </div>

        {/* Info Section */}
        <div className="mt-32 bg-slate-50 rounded-2xl p-10 max-w-4xl mx-auto border border-slate-200">
          <div className="flex items-start gap-6">
            <div className="bg-blue-100 rounded-xl p-3 shrink-0">
              <Shield className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <h3 className="text-xl font-semibold mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Cuenta de Depósito Autorizada
              </h3>
              <div className="space-y-2 text-slate-700 text-sm">
                <p><span className="font-medium">Razón social:</span> JARDINERIA Y COMERCIO THABYETHA SA DE CV</p>
                <p><span className="font-medium">Banco:</span> STP</p>
                <p><span className="font-medium">CLABE:</span> 646180139409481462</p>
              </div>
              <p className="mt-4 text-xs text-slate-500">
                Todos los depósitos de clientes NetCash deben realizarse a esta cuenta.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-16 text-center text-slate-500 border-t border-slate-200 bg-slate-50 mt-32">
        <p className="text-sm font-light">
          © 2025 MBco - Asistente NetCash
        </p>
      </footer>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => {
  return (
    <div className="bg-white rounded-xl p-8 border border-slate-200 hover:border-slate-300 transition-all hover:shadow-medium">
      <div className="mb-4">{icon}</div>
      <h3 className="text-lg font-semibold mb-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        {title}
      </h3>
      <p className="text-slate-600 leading-relaxed text-sm font-light">
        {description}
      </p>
    </div>
  );
};

export default Home;