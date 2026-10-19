# capstone-public

# Capstone

## Uso del programa

### 1. Clonar el repositorio

```bash
git clone https://github.com/RaimundoViel/capstone-public.git
cd capstone-public
```

### 2. Crear el entorno virtual

```bash
python3 -m venv .venv
```

### 3. Activar el entorno virtual

En Linux o WSL:

```bash
source .venv/bin/activate
```

En Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Instalar las dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Ejecutar el programa

Desde la raíz del proyecto:

```bash
python -B -m Heuristica.heuristica_ambulancias
```

### 6. Ejecutar con una semilla específica

```bash
python -B -m Heuristica.heuristica_ambulancias --semilla 42
```

### 7. Ejecutar con una configuración personalizada

```bash
python -B -m Heuristica.heuristica_ambulancias --config ruta/a/config.json
```

### 8. Consultar los argumentos disponibles

```bash
python -B -m Heuristica.heuristica_ambulancias --help
```

### 9. Desactivar el entorno virtual

```bash
deactivate
```

### 10. Actualizar el repositorio

Para descargar los últimos cambios desde GitHub:

```bash
git pull
```

