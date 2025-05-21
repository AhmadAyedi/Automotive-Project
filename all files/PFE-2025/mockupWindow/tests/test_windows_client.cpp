#include "windows_client.h"
#include <gtest/gtest.h>
#include <sstream>
#include <iostream>

// Classe de test
class WindowsClientTest : public ::testing::Test {
protected:
    WindowsClient client;  // Instance de WindowsClient

    // Fonction pour capturer la sortie de la fonction testée
    std::string capture_output(std::function<void()> func) {
        std::streambuf* old_buf = std::cout.rdbuf();
        std::ostringstream output_stream;
        std::cout.rdbuf(output_stream.rdbuf());

        func();

        std::cout.rdbuf(old_buf);
        return output_stream.str();
    }
};

// Test simple pour vérifier l'affichage de la fenêtre du conducteur
TEST_F(WindowsClientTest, DriverWindowPrintsCorrectStatus) {
    std::string result = capture_output([&]() {
        client.driver_window("OPEN");  // Appel de la méthode à tester
    });
    EXPECT_NE(result.find("Driver Window | Status: OPEN"), std::string::npos);  // Vérification que le texte "Driver Window | Status: OPEN" est présent
}
