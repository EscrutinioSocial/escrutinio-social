describe('Autenticación', () => {
    it('chequear web login', () => {
        cy.visit('/login/');
        cy.contains('Nombre de usuario o DNI');
    });

    it('chequear web fiscales', () => {
        cy.visit('/quiero-ser-fiscal/');
        cy.contains('Quiero ser fiscal de las PASO Nacional 2019');
    });

    it('login-A2-A3-A4', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.DE_username);
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.DE_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de DE
    });
    it('login-A5-A6-A7', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.DEUB_username);
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.DEUB_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de DEUB
    });
    it('login-A8-A9-A10', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.FA_username);
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.FA_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de FA Deberia poder subir actas luego del login?
    });
    it('login-A11-A12-A13', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.UV_username);
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.UV_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de UV Solo visualiza?
    });
    it('login-A15--A26-contraseña-inválida', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.DE_username); //TODO: Agregar para todos los usuarios existentes
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.invalido_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Por favor introduzca un nombre de usuario y una contraseña correctos.');
    });
    it('login-A15--A26-usuario-inválido', () => {
        cy.visit('/login/');
        cy.fixture('usuarios').then((user) => {
            cy.get('#id_username').type(user.invalido_username);
            cy.get('#id_password').first().focus();
            cy.get('#id_password').type(user.DE_pass);
        });
        cy.contains('Identificarse').click();
        cy.contains('Por favor introduzca un nombre de usuario y una contraseña correctos.');
    });

});
