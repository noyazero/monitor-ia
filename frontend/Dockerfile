# Usar una imagen de Node para tener 'npx'
FROM node:18-alpine

# Instalar un servidor web simple
RUN npm install -g http-server

# Establecer el directorio
WORKDIR /public

# Copiar el index.html
COPY index.html .

# Exponer el puerto
EXPOSE 3000

# Correr el servidor
CMD [ "http-server", ".", "-p", "3000" ]
