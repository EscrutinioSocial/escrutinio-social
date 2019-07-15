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
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.DE_username, user.DE_pass);
        });
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de DE
    });
    it('login-A5-A6-A7', () => {
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.DEUB_username, user.DEUB_pass);
        });
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de DEUB
    });
    it('login-A8-A9-A10', () => {
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.FA_username, user.FA_pass);
        });
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de FA Deberia poder subir actas luego del login?
    });
    it('login-A11-A12-A13', () => {
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.UV_username, user.UV_pass);
        });
        cy.contains('Cargar resultados de actas'); //Revisar La autenticación de UV Solo visualiza?
    });
    it('login-A15--A26-contraseña-inválida', () => {
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.DE_username, user.invalido_pass); //TODO: Agregar para todos los usuarios existentes
        });
        cy.contains('Por favor introduzca un nombre de usuario y una contraseña correctos.');
    });
    it('login-A15--A26-usuario-inválido', () => {
        cy.fixture('usuarios').then((user) => {
            cy.loginAs(user.invalido_username, user.DE_pass);
        });
        cy.contains('Por favor introduzca un nombre de usuario y una contraseña correctos.');
    });

});
