import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import confusion_matrix
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.layers import Dense, Flatten, BatchNormalization, Input
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping


# =========================
# Lire dataset MIT-BIH
# =========================
raw_data = pd.read_csv("mitbih_train.csv", header=None)
D = raw_data.values

print("Dataset shape :", D.shape)

# Dernière colonne = label
print("Distribution labels :")
print(raw_data.iloc[:, -1].value_counts().sort_index())


# =========================
# Garder seulement 0 et 1
# 0 = normal
# 1 = anormal
# =========================
df_0 = D[D[:, -1] == 0]
df_1 = D[D[:, -1] == 1]

print("Classe 0 :", df_0.shape)
print("Classe 1 :", df_1.shape)


# =========================
# Equilibrer les classes
# =========================
n = min(len(df_0), len(df_1))

idx_0 = np.random.choice(len(df_0), n, replace=False)
idx_1 = np.random.choice(len(df_1), n, replace=False)

df_0_balanced = df_0[idx_0]
df_1_balanced = df_1[idx_1]

D1 = np.concatenate([df_0_balanced, df_1_balanced])
np.random.shuffle(D1)

print("Dataset équilibré :", D1.shape)


# =========================
# Split train / val / test
# =========================
number_of_rows = D1.shape[0]

train_indices = np.random.choice(
    number_of_rows,
    size=int(number_of_rows * 0.7),
    replace=False
)

label_train = D1[train_indices, -1].astype("int32")
data_train = D1[train_indices, :-1].astype("float32")

D1_rest = np.delete(D1, train_indices, axis=0)

number_of_rows = D1_rest.shape[0]

val_indices = np.random.choice(
    number_of_rows,
    size=int(number_of_rows * 0.5),
    replace=False
)

label_val = D1_rest[val_indices, -1].astype("int32")
data_val = D1_rest[val_indices, :-1].astype("float32")

D1_test = np.delete(D1_rest, val_indices, axis=0)

label_test = D1_test[:, -1].astype("int32")
data_test = D1_test[:, :-1].astype("float32")


# Shape pour Conv1D : (samples, 187, 1)
data_train = np.expand_dims(data_train, axis=2)
data_val = np.expand_dims(data_val, axis=2)
data_test = np.expand_dims(data_test, axis=2)

print("Train :", label_train.shape, data_train.shape)
print("Val   :", label_val.shape, data_val.shape)
print("Test  :", label_test.shape, data_test.shape)


# =========================
# Evaluation
# =========================
def evaluate_model(history, X_test, y_test, model):
    scores = model.evaluate(X_test, y_test, verbose=0)
    print("Accuracy: %.2f%%" % (scores[1] * 100))

    plt.figure()
    plt.plot(history.history["accuracy"])
    plt.plot(history.history["val_accuracy"])
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.title("Model - Accuracy")
    plt.legend(["Training", "Validation"], loc="lower right")
    plt.show()

    plt.figure()
    plt.plot(history.history["loss"])
    plt.plot(history.history["val_loss"])
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Model - Loss")
    plt.legend(["Training", "Validation"], loc="upper right")
    plt.show()

    prediction_proba = model.predict(X_test)
    prediction = np.argmax(prediction_proba, axis=1)

    cm = confusion_matrix(y_test, prediction)
    print("Matrice de confusion :")
    print(cm)


# =========================
# CNN 1D
# =========================
def network_CNN(X_train):
    im_shape = (X_train.shape[1], 1)

    inputs_cnn = Input(shape=im_shape, name="inputs_cnn")

    conv1d_1 = layers.Conv1D(filters=32, kernel_size=3)(inputs_cnn)
    batch_normalization = BatchNormalization()(conv1d_1)
    max_pooling1d = layers.MaxPooling1D(2, padding="same")(batch_normalization)

    conv1d_2 = layers.Conv1D(filters=64, kernel_size=3)(max_pooling1d)
    batch_normalization_1 = BatchNormalization()(conv1d_2)
    max_pooling1d_1 = layers.MaxPooling1D(2, padding="same")(batch_normalization_1)

    flatten = Flatten()(max_pooling1d_1)

    dense = Dense(512, activation="relu")(flatten)
    dense_1 = Dense(128, activation="relu")(dense)
    dense_2 = Dense(64, activation="relu")(dense_1)
    dense_3 = Dense(32, activation="relu")(dense_2)

    main_output = Dense(2, activation="softmax")(dense_3)

    model = Model(inputs=inputs_cnn, outputs=main_output)

    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    return model


model1 = network_CNN(data_train)
print(model1.summary())


# =========================
# Callbacks
# =========================
save_path = "checkpoint_1"

model_checkpoint_callback = ModelCheckpoint(
    filepath=save_path,
    save_weights_only=True,
    monitor="val_accuracy",
    mode="max",
    save_best_only=True
)

early_stop = EarlyStopping(
    monitor="val_loss",
    patience=3,
    restore_best_weights=True
)


# =========================
# Training
# =========================
history = model1.fit(
    data_train,
    label_train,
    epochs=20,
    batch_size=32,
    validation_data=(data_val, label_val),
    callbacks=[model_checkpoint_callback, early_stop]
)


# =========================
# Evaluation + sauvegarde
# =========================
evaluate_model(history, data_test, label_test, model1)

model1.save("model_cnn_ecg_0_1.h5")
print("Modèle CNN sauvegardé : model_cnn_ecg_0_1.h5")