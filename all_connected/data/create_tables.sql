DROP DATABASE IF EXISTS `lexi_db`;
CREATE DATABASE `lexi_db`;

USE `lexi_db`;

DROP TABLE IF EXISTS `responses`;
DROP TABLE IF EXISTS `users`;

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(50) PRIMARY KEY, -- randomly generated
    username VARCHAR(50),
    email VARCHAR(50),
    status ENUM('active', 'inactive') DEFAULT 'active'
)
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS responses (
    -- response info
    response_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50),
    channel_id VARCHAR(50),

    general_area ENUM(
        'The Quint (Beebe, Cazenove, Pomeroy, Shafer, Munger)', 
        'East Side (Bates, Freeman, McAfee)', 
        'Stone Davis', 
        'Tower Court (East, West, Claflin, Severance)', 
        'Academic Quad (Green, Founders, PNE/PNW, Jewett)', 
        'Science Center', 
        'Modular Units', 
        'Lulu Chow Wang Campus Center', 
        'Keohane Sports Center (KSC)', 
        'Acorns', 
        'Billings', 
        'Harambee House', 
        'Slater House', 
        'Lake House', 
        'On the Local Motion', 
        'Bus stops (Chapel, Lulu, Founders)', 
        'Shakespeare Houses', 
        'TZE House', 
        'ZA House', 
        'French House', 
        'Casa Cervantes', 
        'Others'
    ),
    loco_time TIMESTAMP, 
    general_area_others VARCHAR(255),

    exact_location TEXT,

    language_heard VARCHAR(100),

    is_speaker BOOLEAN DEFAULT FALSE,
    heard_in_media BOOLEAN DEFAULT FALSE,
    family_speaks BOOLEAN DEFAULT FALSE,
    currently_learning BOOLEAN DEFAULT FALSE,
    friends_use BOOLEAN DEFAULT FALSE,
    same_language_family BOOLEAN DEFAULT FALSE,
    language_familiarity_others BOOLEAN DEFAULT FALSE,
    language_familiarity_others_description VARCHAR(255),

    submission_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY (channel_id), 
    FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL
)
ENGINE = InnoDB;